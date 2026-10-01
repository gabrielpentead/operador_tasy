# -*- coding: utf-8 -*-
"""
Detector de incidentes críticos.

Ideia central: um painel reiniciando sozinho é auto-recuperação NORMAL. Vários
painéis da MESMA unidade em recuperação automática (ou reportando erro de
conexão do Tasy) num intervalo curto indica um problema MAIOR — provavelmente o
Tasy ou a infra daquela unidade. Aí sim vale alertar o plantão.

Princípios:
  - Camada 100% de observação. NÃO toca no operador, na automação nem no Tasy.
  - As notificações vindas dos handlers WebSocket são não-bloqueantes: só
    empilham numa fila. Todo o trabalho pesado (agrupar, decidir, enviar e-mail)
    roda num worker próprio, para nunca segurar a thread do WebSocket.
  - Conexão SQLite PRÓPRIA do worker — não compartilha a conexão do servidor
    entre threads.
  - Reinícios PROGRAMADOS são ignorados (só 'Recuperação automática' conta),
    então o reinício diário das 06:50 e os comandos do dashboard não alarmam.

Ajuste fino via constantes abaixo.
"""

import os
import re
import time
import queue
import sqlite3
import logging
import threading
from math import ceil
from datetime import datetime

from monitoring import incident_store

logger = logging.getLogger("TasyServerCentral")


def _envf(nome, padrao):
    """Lê um parâmetro do ambiente (para calibrar sem mexer no código)."""
    try:
        return type(padrao)(os.getenv(nome, padrao))
    except (TypeError, ValueError):
        return padrao

# ── Parâmetros de detecção (ajustáveis por ambiente TASY_ALERT_*) ────────────
JANELA_S            = _envf('TASY_ALERT_JANELA_S', 120)      # janela p/ agrupar sinais de um painel
CRIT_MIN_PAINEIS    = _envf('TASY_ALERT_MIN_PAINEIS', 3)     # nº mínimo de painéis distintos
CRIT_PCT            = _envf('TASY_ALERT_PCT', 0.30)          # ou este % dos conectados da unidade
CONSOLIDACAO_S      = _envf('TASY_ALERT_CONSOLIDACAO_S', 30) # juntar afetados antes do 1º e-mail
# Silêncio para declarar recuperado. Alto de propósito (10 min): num Tasy
# instável (indo e voltando), enquanto houver reinícios de tempos em tempos o
# incidente CONTINUA aberto — em vez de "recuperar" numa janela boa curta e
# reabrir logo depois, gerando e-mails de abre/recupera repetidos.
SILENCIO_RECUP_S    = _envf('TASY_ALERT_SILENCIO_S', 600)
# Depois que um incidente é encerrado, ignora reabertura na mesma unidade por
# este tempo: os "restos" do mesmo episódio (alguns reinícios logo após a
# calmaria) não disparam um novo alerta de abertura.
COOLDOWN_REABERTURA_S = _envf('TASY_ALERT_COOLDOWN_S', 300)
GRACA_BOOT_S        = _envf('TASY_ALERT_GRACA_BOOT_S', 90)   # ignora sinais logo após o boot
TICK_S              = _envf('TASY_ALERT_TICK_S', 5)          # frequência de revisão dos incidentes

# Só este motivo de reinício conta como sinal de problema. Os demais são
# esperados e NÃO podem gerar alerta.
MOTIVO_RECUPERACAO  = 'Recuperação automática'

# Texto do diálogo de erro do Tasy que o agente já loga em _is_healthy.
_TASY_ERRO_MARCAS = ('conectar-se com o servidor', 'não foi possível conectar')


def _extrair_unidade(nome: str) -> str:
    """Deriva a 'unidade' a partir do nome do painel (ex.: 'Unidade II - ...')."""
    if not nome:
        return 'Geral'
    m = re.search(r'unidade\s+([ivx]+|\d+)', nome, re.IGNORECASE)
    return f"Unidade {m.group(1).upper()}" if m else 'Geral'


class _Incidente:
    def __init__(self, unidade, agora_mono):
        self.unidade = unidade
        self.aberto_em = agora_mono
        self.ultimo_sinal = agora_mono
        self.primeira_ocorrencia = datetime.now()
        self.ultima_ocorrencia = datetime.now()
        self.afetados = set()          # ids de operador
        self.nomes = {}                # id -> nome (para o e-mail)
        self.tem_sinal_tasy = False
        self.estado = 'acumulando'     # 'acumulando' -> 'notificado'
        self.persist_id = None         # id na tabela incidentes (auditoria)

    def resumo(self):
        return {
            'unidade': self.unidade,
            'afetados': len(self.afetados),
            'nomes': sorted(self.nomes.values()),
            'primeira': self.primeira_ocorrencia.strftime('%H:%M:%S'),
            'ultima': self.ultima_ocorrencia.strftime('%H:%M:%S'),
            'tasy': self.tem_sinal_tasy,
        }


class IncidentDetector:
    def __init__(self, db_path, get_email_config, get_connected_ids, mailer, logger=logger):
        self.db_path = db_path
        self.get_email_config = get_email_config     # callable -> EmailConfig
        self.get_connected_ids = get_connected_ids   # callable -> list[str]
        self.mailer = mailer                         # AlertMailer
        self.log = logger

        self._fila = queue.Queue()
        self._sinais = {}          # unidade -> list[(mono_ts, operador_id, classe)]
        self._incidentes = {}      # unidade -> _Incidente
        self._recuperado_em = {}   # unidade -> mono_ts do último encerramento (cooldown)
        self._mapa_unidade = {}    # operador_id -> unidade (cache)
        self._nome = {}            # operador_id -> nome (cache)
        self._mapa_carregado_em = 0.0
        self._iniciado_em = time.monotonic()
        self._parar = False
        self._conn = None

    # ── API chamada pelos handlers WebSocket (rápida, não bloqueia) ──────────
    def notify_reinicio(self, operador_id, motivo):
        if motivo == MOTIVO_RECUPERACAO:
            self._enfileirar('reinicio', operador_id)

    def notify_erro(self, operador_id, titulo, detalhe):
        texto = f"{titulo or ''} {detalhe or ''}".lower()
        if any(marca in texto for marca in _TASY_ERRO_MARCAS):
            self._enfileirar('tasy', operador_id)

    def notify_offline(self, operador_id):
        self._enfileirar('offline', operador_id)

    def notify_online(self, operador_id):
        self._enfileirar('online', operador_id)

    def _enfileirar(self, classe, operador_id):
        try:
            self._fila.put_nowait((classe, operador_id, time.monotonic()))
        except Exception:
            pass  # nunca deixar isso afetar o chamador (thread do WebSocket)

    # ── Ciclo de vida ────────────────────────────────────────────────────────
    def start(self):
        threading.Thread(target=self._worker, daemon=True, name="IncidentDetector").start()
        self.log.info("Detector de incidentes iniciado.")

    def stop(self):
        self._parar = True

    # ── Worker (única thread que mexe no estado) ─────────────────────────────
    def _worker(self):
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        incident_store.ensure_table(self._conn)
        self._carregar_mapa()
        while not self._parar:
            try:
                try:
                    classe, oid, ts = self._fila.get(timeout=TICK_S)
                    self._processar_sinal(classe, oid, ts)
                except queue.Empty:
                    pass
                self._tick()
            except Exception as e:
                self.log.error(f"Detector de incidentes: erro no worker: {e}", exc_info=True)
                time.sleep(1)

    def _carregar_mapa(self):
        """Cache id->unidade/nome, recarregado a cada 5 min."""
        try:
            cur = self._conn.cursor()
            cur.execute("SELECT id, nome FROM operadores WHERE deleted IS NOT 1")
            for row in cur.fetchall():
                self._nome[row['id']] = row['nome']
                self._mapa_unidade[row['id']] = _extrair_unidade(row['nome'])
            self._mapa_carregado_em = time.monotonic()
        except Exception as e:
            self.log.warning(f"Detector: falha ao carregar mapa de operadores: {e}")

    def _unidade_de(self, oid):
        if time.monotonic() - self._mapa_carregado_em > 300:
            self._carregar_mapa()
        if oid not in self._mapa_unidade:
            # painel novo/desconhecido: tenta buscar; se não achar, cai em 'Geral'
            try:
                cur = self._conn.cursor()
                cur.execute("SELECT nome FROM operadores WHERE id = ?", (oid,))
                r = cur.fetchone()
                nome = r['nome'] if r else None
            except Exception:
                nome = None
            self._nome[oid] = nome or oid[:8]
            self._mapa_unidade[oid] = _extrair_unidade(nome)
        return self._mapa_unidade[oid]

    def _em_graca_de_boot(self):
        return (time.monotonic() - self._iniciado_em) < GRACA_BOOT_S

    def _processar_sinal(self, classe, oid, ts):
        unidade = self._unidade_de(oid)

        # 'online' fecha nada sozinho, mas marca atividade; a recuperação é por
        # silêncio. Sinais de problema alimentam a janela.
        if classe == 'online':
            return
        if self._em_graca_de_boot():
            return

        lista = self._sinais.setdefault(unidade, [])
        lista.append((ts, oid, classe))
        # poda a janela
        corte = ts - JANELA_S
        lista[:] = [s for s in lista if s[0] >= corte]

        # painéis distintos com sinal de problema na janela
        distintos = {s[1] for s in lista}
        limiar = self._limiar(unidade)

        inc = self._incidentes.get(unidade)
        if inc is None:
            if len(distintos) >= limiar:
                # Cooldown: se acabou de encerrar um incidente nesta unidade,
                # não reabre logo — são os "restos" do mesmo episódio. Só volta
                # a poder alertar depois do cooldown.
                desde_recup = ts - self._recuperado_em.get(unidade, float('-inf'))
                if desde_recup < COOLDOWN_REABERTURA_S:
                    self.log.info(
                        f"↩️ {unidade}: {len(distintos)} painéis com sinal, mas dentro do "
                        f"cooldown de {COOLDOWN_REABERTURA_S}s pós-recuperação — não reabre.")
                    return
                inc = _Incidente(unidade, ts)
                self._incidentes[unidade] = inc
                self.log.warning(
                    f"🚨 Incidente ABERTO em {unidade}: {len(distintos)} painéis "
                    f"com sinal de falha em {JANELA_S}s (limiar {limiar}).")
                self._alimentar_incidente(inc, lista)
        else:
            self._alimentar_incidente(inc, lista)
            inc.ultimo_sinal = ts

    def _alimentar_incidente(self, inc, lista):
        for ts, oid, classe in lista:
            inc.afetados.add(oid)
            inc.nomes[oid] = self._nome.get(oid, oid[:8])
            if classe == 'tasy' or classe == 'reinicio':
                inc.tem_sinal_tasy = inc.tem_sinal_tasy or (classe == 'tasy')
        inc.ultima_ocorrencia = datetime.now()
        inc.ultimo_sinal = time.monotonic()

    def _limiar(self, unidade):
        """max(mínimo absoluto, % dos conectados daquela unidade)."""
        try:
            conectados = self.get_connected_ids() or []
        except Exception:
            conectados = []
        n_unidade = sum(1 for cid in conectados if self._mapa_unidade.get(cid) == unidade)
        return max(CRIT_MIN_PAINEIS, ceil(CRIT_PCT * n_unidade)) if n_unidade else CRIT_MIN_PAINEIS

    def _tick(self):
        agora = time.monotonic()
        for unidade, inc in list(self._incidentes.items()):
            # 1) hora de mandar o e-mail de abertura (após consolidar)
            if inc.estado == 'acumulando' and (agora - inc.aberto_em) >= CONSOLIDACAO_S:
                inc.estado = 'notificado'
                self._enviar_abertura(inc)
            # 2) silêncio prolongado => recuperado
            if (agora - inc.ultimo_sinal) >= SILENCIO_RECUP_S:
                if inc.estado == 'notificado':
                    self._enviar_recuperacao(inc, agora)
                self._incidentes.pop(unidade, None)
                self._sinais.pop(unidade, None)
                self._recuperado_em[unidade] = agora   # inicia o cooldown de reabertura
                self.log.info(f"✅ Incidente em {unidade} encerrado (silêncio de {SILENCIO_RECUP_S}s).")

    def _enviar_abertura(self, inc):
        resumo = inc.resumo()
        # Persiste ANTES de enviar: a trilha de auditoria não pode depender de o
        # e-mail ter saído (e um envio lento não pode segurar a gravação).
        tipo = 'tasy_unidade' if resumo['tasy'] else 'paineis_instaveis'
        inc.persist_id = incident_store.registrar_aberto(
            self._conn, tipo, resumo['unidade'],
            inc.primeira_ocorrencia.strftime('%Y-%m-%d %H:%M:%S'),
            afetados=resumo['afetados'], detalhe={'nomes': resumo['nomes']})
        try:
            self.mailer.enviar_abertura(self.get_email_config(), self.db_path, resumo)
        except Exception as e:
            self.log.error(f"Falha ao enviar alerta de abertura: {e}")

    def _enviar_recuperacao(self, inc, agora_mono):
        try:
            dados = inc.resumo()
            dur_s = int(agora_mono - inc.aberto_em - SILENCIO_RECUP_S)
            dados['duracao_min'] = max(1, round(dur_s / 60))
            # O incidente só fecha após o silêncio: todos os afetados pararam de
            # falhar, portanto todos recuperaram. (Um painel que continuasse em
            # falha manteria o incidente aberto.)
            dados['recuperados'] = dados['afetados']
            incident_store.registrar_recuperado(
                self._conn, inc.persist_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            self.mailer.enviar_recuperacao(self.get_email_config(), self.db_path, dados)
        except Exception as e:
            self.log.error(f"Falha ao enviar alerta de recuperação: {e}")
