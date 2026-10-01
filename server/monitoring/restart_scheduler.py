# -*- coding: utf-8 -*-
"""
Agendador dos reinícios automáticos dos painéis.

Substitui o horário fixo (06:50) que antes só existia implicitamente: agora a
programação mora na tabela `reinicios_programados` (gerenciável pela tela de
Configurações > Reinícios, somente admin) e este módulo é quem, no horário
certo, dispara o comando — reaproveitando o MESMO caminho que o botão manual
do dashboard já usa (evento 'comando', comando='reiniciar'), então o agente
não precisa de nenhuma mudança para responder a um reinício programado pelo
servidor.

Princípios (mesmos do TasyHostMonitor/IncidentDetector):
  - Camada isolada, thread própria, nunca levanta exceção para fora.
  - Conexão SQLite PRÓPRIA do worker — não compartilha a conexão do request.
  - O operador continua independente: se estiver offline no minuto do
    disparo, simplesmente não recebe o comando (não há fila nem retry) e
    segue funcionando normalmente por conta própria até a próxima conexão.
    O servidor só é necessário para ENTREGAR o comando, nunca para o operador
    decidir se deve rodar.
"""

import time
import sqlite3
import logging
import threading
from datetime import datetime

logger = logging.getLogger("TasyServerCentral")

# Intervalo de checagem. Menor que 60s para não perder o minuto configurado,
# com folga suficiente para não pesar no banco.
TICK_S = 20


class RestartScheduler:
    def __init__(self, db_path, socketio, connected_operators, logger=logger):
        self.db_path = db_path
        self.socketio = socketio
        self.connected_operators = connected_operators
        self.log = logger
        self._parar = False

    # ── Ciclo de vida ────────────────────────────────────────────────────────
    def start(self):
        threading.Thread(target=self._loop, daemon=True, name="RestartScheduler").start()
        self.log.info(f"Agendador de reinícios iniciado (checagem a cada {TICK_S}s).")

    def stop(self):
        self._parar = True

    # ── Laço ─────────────────────────────────────────────────────────────────
    def _loop(self):
        while not self._parar:
            try:
                self._passo()
            except Exception as e:
                self.log.error(f"Agendador de reinícios: erro no laço: {e}", exc_info=True)
            dormido = 0.0
            while not self._parar and dormido < TICK_S:
                time.sleep(min(1.0, TICK_S - dormido))
                dormido += 1.0

    def _passo(self):
        agora = datetime.now()
        hhmm = agora.strftime('%H:%M')
        hoje = agora.strftime('%Y-%m-%d')
        dia_semana = agora.weekday()  # 0=segunda .. 6=domingo

        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(
                '''SELECT * FROM reinicios_programados
                   WHERE ativo = 1 AND horario = ?''', (hhmm,))
            candidatos = cur.fetchall()

            for row in candidatos:
                dias = self._parse_dias(row['dias_semana'])
                if dia_semana not in dias:
                    continue
                # Já disparado hoje? (dedupe contra o tick rodar mais de uma
                # vez dentro do mesmo minuto configurado)
                disparado_em = row['disparado_em'] or ''
                if disparado_em.startswith(hoje):
                    continue
                self._disparar(conn, row)
        finally:
            conn.close()

    @staticmethod
    def _parse_dias(texto):
        try:
            return {int(p) for p in (texto or '').split(',') if p.strip() != ''}
        except ValueError:
            return set()

    # ── Disparo ──────────────────────────────────────────────────────────────
    def _disparar(self, conn, row):
        reinicio_id = row['id']
        target = row['target'] or 'ambos'
        agora_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        destinatarios = list(self.connected_operators.keys())
        for operador_id in destinatarios:
            try:
                self.socketio.emit('comando', {'comando': 'reiniciar', 'target': target},
                                   room=operador_id)
                # Marca que o próximo evento de reinício deste operador é
                # esperado (veio do agendamento, não de um clique manual no
                # dashboard) — o handle_evento_operador usa isso para rotular
                # o histórico corretamente. Some sozinha se o operador
                # desconectar (o dicionário inteiro é descartado).
                if operador_id in self.connected_operators:
                    self.connected_operators[operador_id]['origem_comando_pendente'] = {
                        'origem': 'agendado',
                        'desde': datetime.now(),
                    }
            except Exception as e:
                self.log.warning(f"Falha ao enviar reinício programado ao operador {operador_id}: {e}")

        try:
            conn.execute('UPDATE reinicios_programados SET disparado_em = ? WHERE id = ?',
                        (agora_str, reinicio_id))
            conn.commit()
        except sqlite3.Error as e:
            self.log.warning(f"Falha ao registrar disparo do reinício programado {reinicio_id}: {e}")

        self.log.info(
            f"⏰ Reinício programado #{reinicio_id} ({row['horario']}, alvo={target}) disparado "
            f"para {len(destinatarios)} operador(es) conectado(s).")
