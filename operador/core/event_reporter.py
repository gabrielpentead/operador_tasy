#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Repórter de eventos de monitoramento (reinícios e erros) para o servidor.

CAMADA ISOLADA — de propósito. Este módulo apenas OBSERVA e ENVIA; nunca
interfere no fluxo de automação, login, Edge ou TTS. Regras invioláveis:

  - Nenhum método aqui pode levantar exceção para quem chamou. Tudo é
    envolvido em try/except que engole a falha (com log de debug, no máximo).
  - Se o WebSocket estiver caído, os eventos ficam num buffer LIMITADO
    (deque com maxlen) e vão no próximo flush; nada bloqueia, nada acumula
    sem teto.
  - Erros repetidos idênticos, dentro de uma mesma janela de flush, viram
    contagem no próprio evento em vez de N eventos — evita "despejar log".

O servidor persiste os eventos (tabela eventos_operador) e os serve para a
visão detalhada do painel.
"""

import logging
import threading
from datetime import datetime
from collections import deque

logger = logging.getLogger("TasyOperador.EventReporter")

# Evento do WebSocket usado para enviar o lote. O servidor escuta o mesmo nome.
_WS_EVENT = 'evento_operador'


class EventReporter:
    def __init__(self, ws_getter, id_getter, max_buffer: int = 100):
        """ws_getter: callable -> WebSocketClient|None; id_getter: callable -> str."""
        self._ws_getter = ws_getter
        self._id_getter = id_getter
        self._buffer = deque(maxlen=max_buffer)
        self._lock = threading.Lock()

    # ── Registro de eventos ──────────────────────────────────────────────

    def registrar_reinicio(self, motivo, alvo, inicio, fim, sucesso):
        """Enfileira um evento de reinicialização e tenta enviar na hora.

        Reinícios são raros e importantes: além de bufferizar, chamamos flush()
        para que apareçam no painel prontamente.
        """
        try:
            duracao = max(0, int((fim - inicio).total_seconds()))
            self._enfileirar({
                'tipo': 'reinicio',
                'nivel': 'sucesso' if sucesso else 'falha',
                'titulo': motivo or 'Reinicialização',
                'detalhe': f"Alvo: {alvo}",
                'ocorrido_em': inicio.strftime('%Y-%m-%d %H:%M:%S'),
                'dados': {
                    'motivo': motivo,
                    'alvo': str(alvo),
                    'inicio': inicio.strftime('%H:%M:%S'),
                    'fim': fim.strftime('%H:%M:%S'),
                    'duracao_s': duracao,
                    'resultado': 'sucesso' if sucesso else 'falha',
                },
            })
            self.flush()
        except Exception as e:
            logger.debug(f"registrar_reinicio ignorado: {e}")

    def registrar_erro(self, nivel, tipo_erro, mensagem, ocorrido_em=None):
        """Enfileira um erro. Idênticos na mesma janela de flush viram contagem."""
        try:
            ts = ocorrido_em or datetime.now()
            msg = (mensagem or '').strip()
            assinatura = f"{nivel}|{tipo_erro}|{msg[:140]}"
            with self._lock:
                # se um idêntico ainda não foi enviado, só incrementa a contagem
                for ev in self._buffer:
                    if ev.get('_assinatura') == assinatura:
                        ev['dados']['ocorrencias'] = ev['dados'].get('ocorrencias', 1) + 1
                        return
                self._buffer.append({
                    '_assinatura': assinatura,
                    'tipo': 'erro',
                    'nivel': nivel,
                    'titulo': tipo_erro,
                    'detalhe': msg[:400],
                    'ocorrido_em': ts.strftime('%Y-%m-%d %H:%M:%S'),
                    'dados': {'tipo_erro': tipo_erro, 'ocorrencias': 1},
                })
        except Exception as e:
            logger.debug(f"registrar_erro ignorado: {e}")

    # ── Envio ────────────────────────────────────────────────────────────

    def _enfileirar(self, evento):
        with self._lock:
            self._buffer.append(evento)

    def flush(self):
        """Envia o que estiver no buffer, se o WebSocket estiver conectado.

        Se não houver conexão, mantém no buffer para a próxima tentativa. Só
        remove do buffer o que foi efetivamente entregue ao send_message.
        """
        try:
            ws = self._ws_getter()
            if not ws or not ws.is_connected():
                return
            with self._lock:
                if not self._buffer:
                    return
                lote = list(self._buffer)
                self._buffer.clear()
            # Limpa o campo interno de assinatura antes de mandar
            eventos = []
            for ev in lote:
                ev = {k: v for k, v in ev.items() if k != '_assinatura'}
                eventos.append(ev)
            ws.send_message(_WS_EVENT, {
                'id': self._id_getter(),
                'eventos': eventos,
            })
        except Exception as e:
            logger.debug(f"flush de eventos ignorado: {e}")


class ErrorCaptureHandler(logging.Handler):
    """Handler de logging que espelha erros para o EventReporter.

    Passivo: não altera formatação, propagação nem nada do logging existente —
    apenas escuta records de nível ERROR/CRITICAL e os repassa ao repórter.
    """

    def __init__(self, reporter: EventReporter, level=logging.ERROR):
        super().__init__(level)
        self._reporter = reporter

    def emit(self, record):
        try:
            nivel = 'critico' if record.levelno >= logging.CRITICAL else 'erro'
            # nome curto do logger de origem, ex.: 'TasyOperador.TasyAutomation' -> 'TasyAutomation'
            tipo_erro = record.name.split('.')[-1]
            self._reporter.registrar_erro(
                nivel, tipo_erro, record.getMessage(),
                ocorrido_em=datetime.fromtimestamp(record.created))
        except Exception:
            # Um handler de logging jamais pode derrubar quem logou.
            pass


def anexar_captura_de_erros(reporter: EventReporter):
    """Anexa o ErrorCaptureHandler à raiz de loggers do agente ('TasyOperador').

    Todos os módulos usam loggers filhos de 'TasyOperador', que propagam para
    ela — então um único handler aqui capta os erros de todo o agente.
    """
    try:
        logging.getLogger("TasyOperador").addHandler(ErrorCaptureHandler(reporter))
    except Exception as e:
        logger.debug(f"não foi possível anexar captura de erros: {e}")
