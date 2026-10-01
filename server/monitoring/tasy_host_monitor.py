# -*- coding: utf-8 -*-
"""
Monitor de disponibilidade do host do Tasy.

Mede a queda do Tasy DIRETAMENTE, acessando o host (teste TCP na porta), em vez
de inferir pelo comportamento dos painéis. É o sinal autoritativo de "Tasy caiu".

Princípios:
  - Camada 100% de observação. NÃO toca no operador, na automação nem no Tasy.
  - Thread própria; nunca levanta exceção para fora; envio de e-mail reusa o
    mailer (mesmos destinatários e SMTP dos outros alertas).
  - Regra anti-falso-positivo importante: só dispara alerta de INDISPONÍVEL
    depois de ter observado o host DISPONÍVEL ao menos uma vez. Assim, rodar o
    servidor fora da rede do hospital (onde o host nem resolve) NÃO gera alarme:
    ele nunca chega a ficar "no ar", então não há transição no-ar→fora-do-ar.
  - Debounce nos dois sentidos: N falhas seguidas p/ declarar queda; M sucessos
    seguidos p/ declarar recuperação. Um blip isolado não alarma.
"""

import ssl
import time
import socket
import sqlite3
import logging
import threading
import urllib.request
import urllib.error
from datetime import datetime

from monitoring import incident_store

logger = logging.getLogger("TasyServerCentral")

# Contexto TLS que NÃO valida o certificado. Isto é uma SONDA de disponibilidade,
# não um canal de dados: só queremos saber se o Tasy responde. Sem isso, um
# certificado interno/expirado do Tasy geraria "fora do ar" falso — quando na
# verdade o servidor está de pé (o handshake TLS aconteceu). Nenhum dado
# sensível trafega aqui.
_CTX_SEM_VERIFICACAO = ssl.create_default_context()
_CTX_SEM_VERIFICACAO.check_hostname = False
_CTX_SEM_VERIFICACAO.verify_mode = ssl.CERT_NONE


class TasyHostMonitor:
    # Estados internos
    DESCONHECIDO = 'desconhecido'   # ainda não vimos o host no ar
    NO_AR        = 'no_ar'
    FORA         = 'fora'

    def __init__(self, cfg, db_path, get_email_config, mailer, logger=logger):
        self.cfg = cfg                              # TasyMonitorConfig
        self.db_path = db_path
        self.get_email_config = get_email_config    # callable -> EmailConfig
        self.mailer = mailer                        # módulo alert_mailer
        self.log = logger

        self._estado = self.DESCONHECIDO
        self._falhas = 0
        self._sucessos = 0
        self._caiu_em = None                        # datetime de quando declarou queda
        self._persist_id = None                     # id na tabela incidentes
        self._parar = False

    def _persistir(self, fn):
        """Roda uma escrita de auditoria com conexão curta e própria. Falha
        aqui nunca atrapalha o alerta."""
        try:
            conn = sqlite3.connect(self.db_path)
            try:
                incident_store.ensure_table(conn)
                return fn(conn)
            finally:
                conn.close()
        except Exception as e:
            self.log.warning(f"Monitor do Tasy: falha ao persistir incidente: {e}")
            return None

    # ── Ciclo de vida ────────────────────────────────────────────────────────
    def start(self):
        if not self.cfg.habilitado:
            self.log.info("Monitor do host do Tasy desativado por configuração.")
            return
        threading.Thread(target=self._loop, daemon=True, name="TasyHostMonitor").start()
        self.log.info(
            f"Monitor do host do Tasy iniciado: GET {self._url()} "
            f"(a cada {self.cfg.intervalo_s}s, timeout {self.cfg.timeout_s}s).")

    def stop(self):
        self._parar = True

    # ── Teste de acesso ──────────────────────────────────────────────────────
    def _url(self) -> str:
        porta = int(self.cfg.porta)
        esquema = 'https' if porta == 443 else 'http'
        base = self.cfg.host if porta in (80, 443) else f"{self.cfg.host}:{porta}"
        caminho = self.cfg.caminho or '/'
        if not caminho.startswith('/'):
            caminho = '/' + caminho
        return f"{esquema}://{base}{caminho}"

    def _acessivel(self) -> bool:
        """Faz uma requisição HTTP e diz se o Tasy REALMENTE respondeu.

        Regra:
          - respondeu com status < 500  → NO AR (inclui 200, 302 de login, 401/403
            — o Tasy está de pé, apenas pedindo autenticação);
          - status >= 500, timeout, conexão recusada/DNS → FORA.

        Por que não TCP simples: numa queda de aplicação o proxy continua aceitando
        a porta 443, e o TCP diria 'no ar' com o Tasy fora — foi o que deixou uma
        queda real passar sem alerta.
        """
        req = urllib.request.Request(self._url(), method='GET',
                                     headers={'User-Agent': 'CentralOperadores-Monitor/1.0'})
        try:
            resp = urllib.request.urlopen(req, timeout=self.cfg.timeout_s,
                                          context=_CTX_SEM_VERIFICACAO)
            try:
                resp.read(64)   # confirma que o corpo começa a fluir; não lê tudo
            except Exception:
                pass
            codigo = getattr(resp, 'status', None) or resp.getcode()
            resp.close()
            return codigo is not None and codigo < 500
        except urllib.error.HTTPError as e:
            # O servidor respondeu com um código de erro HTTP. Só 5xx conta como
            # 'fora' (app quebrada); 4xx significa que o Tasy está de pé.
            return e.code < 500
        except (urllib.error.URLError, socket.timeout, ssl.SSLError, OSError):
            return False
        except Exception as e:
            self.log.warning(f"Monitor do Tasy: erro inesperado na sonda: {type(e).__name__}: {e}")
            return False

    # ── Laço ─────────────────────────────────────────────────────────────────
    def _loop(self):
        # Primeira sondagem imediata para estabelecer a linha de base.
        while not self._parar:
            try:
                self._passo()
            except Exception as e:
                self.log.error(f"Monitor do Tasy: erro no laço: {e}", exc_info=True)
            # dorme em fatias para responder rápido ao stop()
            dormido = 0.0
            while not self._parar and dormido < self.cfg.intervalo_s:
                time.sleep(min(1.0, self.cfg.intervalo_s - dormido))
                dormido += 1.0

    def _passo(self):
        if self._acessivel():
            self._sucessos += 1
            self._falhas = 0
            # Transição para NO_AR
            if self._estado != self.NO_AR and self._sucessos >= self.cfg.sucessos_para_cima:
                anterior = self._estado
                self._estado = self.NO_AR
                if anterior == self.FORA:
                    self._on_recuperado()
                else:
                    self.log.info(f"Host do Tasy acessível ({self.cfg.host}:{self.cfg.porta}).")
        else:
            self._falhas += 1
            self._sucessos = 0
            # Só declara queda se JÁ tínhamos visto o host no ar (evita alarme
            # fora da rede do hospital, onde ele nunca sobe).
            if (self._estado == self.NO_AR and
                    self._falhas >= self.cfg.falhas_para_baixo):
                self._estado = self.FORA
                self._on_caiu()

    # ── Transições ───────────────────────────────────────────────────────────
    def _on_caiu(self):
        self._caiu_em = datetime.now()
        self.log.warning(
            f"🚨 Tasy INDISPONÍVEL — host {self.cfg.host}:{self.cfg.porta} não responde "
            f"({self._falhas} falhas seguidas).")
        self._persist_id = self._persistir(lambda c: incident_store.registrar_aberto(
            c, 'tasy_host', None, self._caiu_em.strftime('%Y-%m-%d %H:%M:%S'),
            detalhe={'host': self.cfg.host, 'porta': self.cfg.porta}))
        try:
            self.mailer.enviar_tasy_down(self.get_email_config(), self.db_path, {
                'host': self.cfg.host,
                'porta': self.cfg.porta,
                'detectado_em': self._caiu_em.strftime('%d/%m/%Y %H:%M:%S'),
            })
        except Exception as e:
            self.log.error(f"Falha ao enviar alerta de Tasy indisponível: {e}")

    def _on_recuperado(self):
        agora = datetime.now()
        dur_min = None
        if self._caiu_em:
            dur_min = max(1, round((agora - self._caiu_em).total_seconds() / 60))
        self.log.info(f"✅ Tasy RESTABELECIDO — host {self.cfg.host}:{self.cfg.porta} respondendo.")
        self._persistir(lambda c: incident_store.registrar_recuperado(
            c, self._persist_id, agora.strftime('%Y-%m-%d %H:%M:%S')))
        self._persist_id = None
        try:
            self.mailer.enviar_tasy_up(self.get_email_config(), self.db_path, {
                'host': self.cfg.host,
                'porta': self.cfg.porta,
                'restabelecido_em': agora.strftime('%d/%m/%Y %H:%M:%S'),
                'duracao_min': dur_min,
            })
        except Exception as e:
            self.log.error(f"Falha ao enviar alerta de Tasy restabelecido: {e}")
        self._caiu_em = None

    # ── Consulta (para outros módulos correlacionarem, sem acoplar) ──────────
    def esta_fora(self) -> bool:
        return self._estado == self.FORA
