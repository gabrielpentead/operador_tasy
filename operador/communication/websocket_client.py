#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cliente WebSocket para comunicação em tempo real com o servidor
"""

import time
import threading
import logging
from datetime import datetime
from typing import Dict, Callable, Optional, Any
import socketio

from utils.constants import (
    HEARTBEAT_INTERVAL, RECONNECTION_DELAY, MAX_RECONNECTION_DELAY,
    CONNECTION_TIMEOUT, VALID_COMMANDS,
    APP_HEARTBEAT_INTERVAL, WATCHDOG_CHECK_INTERVAL, WATCHDOG_SILENCE_LIMIT
)

logger = logging.getLogger("TasyOperador.WebSocket")

class WebSocketClient:
    """Cliente WebSocket para comunicação em tempo real"""
    
    def __init__(self, server_url: str):
        self.server_url = server_url
        # reconnection=False: a reconexão é feita por UM único dono, o
        # _connection_loop desta classe. A reconexão automática embutida do
        # python-socketio, se ligada, competiria com o loop pelo mesmo objeto e
        # deixava o Client preso num estado inconsistente (a causa das quedas
        # que não voltavam sem reiniciar o operador).
        self.sio = socketio.Client(reconnection=False, logger=False, engineio_logger=False)
        self.connected = False
        self.operator_id = None
        self.operator_name = None
        self.reconnection_delay = RECONNECTION_DELAY

        # ── Estado de diagnóstico/resiliência ────────────────────────────────
        # time.monotonic() não anda para trás com acerto de relógio — ideal para
        # medir intervalos. datetime é usado só para carimbar horário legível.
        self._last_server_contact = 0.0   # último sinal de vida vindo do servidor
        self._connected_since = None      # início da conexão atual (monotonic)
        self._disconnect_time = None      # momento da última queda (monotonic)
        self._reconnect_attempts = 0      # tentativas na rajada de reconexão atual
        self._was_ever_connected = False  # distingue 1ª conexão de reconexão
        self._intentional_disconnect = False  # encerramento pedido pelo próprio operador

        # Callbacks
        self.on_command_callback: Optional[Callable] = None
        self.on_config_update_callback: Optional[Callable] = None
        self.on_reset_callback: Optional[Callable] = None
        self.on_connected_callback: Optional[Callable] = None
        self.on_disconnected_callback: Optional[Callable] = None

        # Setup de eventos
        self._setup_events()
    
    def _setup_events(self):
        """Configura os eventos do WebSocket"""
        
        @self.sio.event
        def connect():
            agora = time.monotonic()
            self._last_server_contact = agora
            self.connected = True
            self.reconnection_delay = RECONNECTION_DELAY

            # Se já esteve conectado antes, isto é uma RECONEXÃO: registra o
            # tempo que ficou fora do ar e quantas tentativas foram precisas.
            if self._was_ever_connected and self._disconnect_time is not None:
                fora = agora - self._disconnect_time
                logger.info(f"🌐 Reconectado ao servidor WebSocket "
                            f"(ficou fora {fora:.0f}s, {self._reconnect_attempts} tentativa(s)).")
                self._log_diagnostico('RECONECTADO',
                                      fora_do_ar_s=round(fora, 1),
                                      tentativas=self._reconnect_attempts)
            else:
                logger.info("🌐 Conectado ao servidor WebSocket.")

            self._connected_since = agora
            self._was_ever_connected = True
            self._reconnect_attempts = 0
            self._disconnect_time = None

            if self.operator_id:
                self.register_operator()

            if self.on_connected_callback:
                self.on_connected_callback()

        @self.sio.event
        def disconnect():
            self.connected = False
            self._disconnect_time = time.monotonic()
            duracao = (self._disconnect_time - self._connected_since
                       if self._connected_since else None)
            logger.info("🔌 Desconectado do servidor WebSocket."
                        + (f" (conexão durou {duracao:.0f}s)" if duracao else ""))
            self._log_diagnostico('DESCONECTADO',
                                  intencional=self._intentional_disconnect,
                                  duracao_conexao_s=round(duracao, 1) if duracao else None)

            if self.on_disconnected_callback:
                self.on_disconnected_callback()

        @self.sio.event
        def heartbeat_ack(data):
            """Resposta do servidor ao nosso heartbeat — sinal de vida da via."""
            self._last_server_contact = time.monotonic()
        
        @self.sio.event
        def comando(data):
            """Recebe comandos do servidor"""
            self._last_server_contact = time.monotonic()
            try:
                comando = data.get('comando')
                logger.info(f"📩 Comando recebido do painel: '{comando}'")
                
                if comando in VALID_COMMANDS:
                    if self.on_command_callback:
                        self.on_command_callback(comando, data)
                else:
                    logger.warning(f"⚠️ Comando inválido recebido: {comando}")
                    
            except Exception as e:
                logger.error(f"Erro ao processar comando: {e}")

        @self.sio.event
        def comando_reset(data):
            """Recebe comando de reset total (auto-destruição)"""
            try:
                logger.critical("☢️ COMANDO DE RESET RECEBIDO DO SERVIDOR! INICIANDO PROCEDIMENTO DE LIMPEZA.")
                if self.on_reset_callback:
                    self.on_reset_callback()
            except Exception as e:
                logger.error(f"Erro ao processar comando de reset: {e}")
        
        @self.sio.event
        def config_atualizada(data):
            """Recebe atualizações de configuração"""
            self._last_server_contact = time.monotonic()
            try:
                # Mascarar senhas para o log
                log_data = data.copy()
                for key in log_data:
                    if 'password' in key:
                        log_data[key] = '********'
                logger.info(f"🔑 Configurações do operador atualizadas via WebSocket: {log_data}")
                
                if self.on_config_update_callback:
                    self.on_config_update_callback(data)
                    
            except Exception as e:
                logger.error(f"Erro ao processar atualização de config: {e}")
        
        @self.sio.event
        def status_operador(data):
            """Recebe confirmação de status"""
            self._last_server_contact = time.monotonic()
            try:
                logger.debug(f"Status confirmado pelo servidor: {data}")
            except Exception as e:
                logger.error(f"Erro ao processar status: {e}")
    
    def set_command_callback(self, callback: Callable[[str, Dict], None]):
        """Define callback para comandos recebidos"""
        self.on_command_callback = callback
    
    def set_config_update_callback(self, callback: Callable[[Dict], None]):
        """Define callback para atualizações de configuração"""
        self.on_config_update_callback = callback

    def set_reset_callback(self, callback: Callable[[], None]):
        """Define callback para reset total"""
        self.on_reset_callback = callback
    
    def set_connection_callbacks(self, on_connected: Callable = None, on_disconnected: Callable = None):
        """Define callbacks de conexão"""
        self.on_connected_callback = on_connected
        self.on_disconnected_callback = on_disconnected
    
    def connect(self, operator_id: str, operator_name: str) -> bool:
        """Conecta ao servidor WebSocket e mantém tentativas de reconexão eternas"""
        self.operator_id = operator_id
        self.operator_name = operator_name
        self._intentional_disconnect = False

        # Inicia thread dedicada de conexão/monitoramento para não bloquear main thread
        connect_thread = threading.Thread(target=self._connection_loop, daemon=True, name="WebSocketConnectionLoop")
        connect_thread.start()

        # Heartbeat de aplicação + watchdog anti-zumbi (camadas de resiliência).
        # São daemon: morrem junto com o processo, não seguram o encerramento.
        threading.Thread(target=self._heartbeat_loop, daemon=True, name="WebSocketHeartbeat").start()
        threading.Thread(target=self._watchdog_loop, daemon=True, name="WebSocketWatchdog").start()
        return True

    def _connection_loop(self):
        """Loop eterno de conexão e reconexão — ÚNICO dono da reconexão."""
        logger.info(f"🔄 Iniciando loop de conexão WebSocket com {self.server_url}")

        while True:
            if self._intentional_disconnect:
                # Encerramento pedido pelo operador (cleanup): não reconectar.
                break

            if not self.connected:
                try:
                    # Força desconexão prévia se houver estado inconsistente
                    if self.sio.connected:
                        self.sio.disconnect()

                    self._reconnect_attempts += 1
                    self.sio.connect(self.server_url, wait_timeout=CONNECTION_TIMEOUT)
                    # O evento 'connect' irá setar self.connected = True e resetar delays
                except Exception as e:
                    logger.error(f"❌ Falha na conexão WebSocket "
                                 f"(tentativa {self._reconnect_attempts}): {e}")
                    logger.info(f"⏳ Tentando novamente em {self.reconnection_delay:.0f} segundos...")
                    time.sleep(self.reconnection_delay)
                    # Backoff exponencial simples até MAX_RECONNECTION_DELAY
                    self.reconnection_delay = min(self.reconnection_delay * 1.5, MAX_RECONNECTION_DELAY)
            else:
                # Se já está conectado, apenas dorme e verifica novamente depois
                time.sleep(5)
    
    def disconnect(self):
        """Desconecta do servidor (encerramento intencional, sem reconectar)."""
        try:
            self._intentional_disconnect = True
            if self.connected:
                self.sio.disconnect()
            self.connected = False
        except Exception as e:
            logger.error(f"Erro ao desconectar: {e}")
    
    def register_operator(self, extra_data: Dict = None):
        """Registra o operador no servidor (inclui dados de cadastro)"""
        if self.connected and self.operator_id:
            try:
                data = {
                    'id': self.operator_id,
                    'nome': self.operator_name,
                    'timestamp': datetime.now().isoformat()
                }
                if extra_data:
                    data.update(extra_data)
                
                self.sio.emit('registrar_operador', data)
                logger.info(f"📝 Enviando registro para o servidor: '{self.operator_name}' (ID: {self.operator_id})")
            except Exception as e:
                logger.error(f"Erro ao registrar operador: {e}")
    
    def send_command_ack(self, command: str, target: str):
        """Envia confirmação de recebimento de comando"""
        if self.connected and self.operator_id:
            try:
                self.sio.emit('comando_recebido', {
                    'id': self.operator_id,
                    'comando': command,
                    'target': target,
                    'timestamp': datetime.now().isoformat()
                })
            except Exception as e:
                logger.error(f"Erro ao enviar ACK de comando: {e}")

    def send_command_result(self, command: str, target: str, success: bool, message: str):
        """Envia resultado da execução de comando"""
        if self.connected and self.operator_id:
            try:
                self.sio.emit('comando_executado', {
                    'id': self.operator_id,
                    'comando': command,
                    'target': target,
                    'sucesso': success,
                    'mensagem': message,
                    'timestamp': datetime.now().isoformat()
                })
            except Exception as e:
                logger.error(f"Erro ao enviar resultado de comando: {e}")

    def send_status_update(self, status_data: Dict[str, Any]):
        """Envia atualização de status"""
        if self.connected and self.operator_id:
            try:
                update_data = {
                    'id': self.operator_id,
                    'timestamp': datetime.now().isoformat(),
                    **status_data
                }
                self.sio.emit('atualizar_status', update_data)
                logger.debug("📊 Status enviado para servidor")
            except Exception as e:
                logger.error(f"Erro ao enviar status: {e}")
    
    def send_message(self, message_type: str, data: Dict[str, Any]):
        """Envia mensagem genérica para o servidor"""
        if self.connected:
            try:
                message_data = {
                    'operator_id': self.operator_id,
                    'timestamp': datetime.now().isoformat(),
                    **data
                }
                self.sio.emit(message_type, message_data)
                logger.debug(f"📤 Mensagem enviada: {message_type}")
            except Exception as e:
                logger.error(f"Erro ao enviar mensagem: {e}")
    
    def start_heartbeat(self):
        """Compatibilidade: o heartbeat é iniciado automaticamente em connect().

        Mantido como no-op para não quebrar chamadas existentes.
        """
        pass

    def _heartbeat_loop(self):
        """Envia o evento 'heartbeat' periodicamente (contrato já existente no
        servidor, que responde 'heartbeat_ack'). É o sinal de vida de aplicação
        acima do ping/pong do engine.io."""
        while True:
            time.sleep(APP_HEARTBEAT_INTERVAL)
            if self._intentional_disconnect:
                break
            if self.connected and self.operator_id:
                try:
                    self.sio.emit('heartbeat', {'id': self.operator_id})
                except Exception as e:
                    logger.debug(f"Falha ao enviar heartbeat: {e}")

    def _watchdog_loop(self):
        """Detecta conexão "muda" (zumbi): o socket parece conectado, mas nada
        chega do servidor há tempo demais. Nesse caso força UM disconnect limpo
        — o _connection_loop então reconecta. Não reinicia o operador."""
        while True:
            time.sleep(WATCHDOG_CHECK_INTERVAL)
            if self._intentional_disconnect:
                break
            if not self.connected:
                continue
            silencio = time.monotonic() - self._last_server_contact
            if silencio > WATCHDOG_SILENCE_LIMIT:
                logger.warning(f"⚠️ Watchdog: {silencio:.0f}s sem resposta do servidor "
                               f"(limite {WATCHDOG_SILENCE_LIMIT}s). Forçando reconexão.")
                self._log_diagnostico('ZUMBI_DETECTADO', silencio_s=round(silencio, 1))
                # Garante que o loop vá reconectar mesmo se o disconnect não disparar.
                if self._disconnect_time is None:
                    self._disconnect_time = time.monotonic()
                self.connected = False
                try:
                    self.sio.disconnect()
                except Exception:
                    pass

    def _log_diagnostico(self, evento: str, **dados):
        """Registra ocorrências de conexão para diagnóstico posterior.

        Fica só no log (arquivo do operador), sem tocar na interface do
        dashboard. Linha padronizada e fácil de filtrar por 'CONEXAO'.
        """
        try:
            carimbo = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            partes = ' '.join(f"{k}={v}" for k, v in dados.items() if v is not None)
            logger.info(f"🩺 CONEXAO {evento} [{carimbo}] op={self.operator_id} {partes}".rstrip())
        except Exception:
            pass

    def is_connected(self) -> bool:
        """Retorna se está conectado"""
        return self.connected and self.sio.connected