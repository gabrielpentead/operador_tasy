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
    CONNECTION_TIMEOUT, VALID_COMMANDS
)

logger = logging.getLogger("TasyOperador.WebSocket")

class WebSocketClient:
    """Cliente WebSocket para comunicação em tempo real"""
    
    def __init__(self, server_url: str):
        self.server_url = server_url
        self.sio = socketio.Client(logger=False, engineio_logger=False)
        self.connected = False
        self.operator_id = None
        self.operator_name = None
        self.reconnection_delay = RECONNECTION_DELAY
        
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
            self.connected = True
            self.reconnection_delay = RECONNECTION_DELAY
            logger.info("🌐 Conectado ao servidor WebSocket.")
            
            if self.operator_id:
                self.register_operator()

            if self.on_connected_callback:
                self.on_connected_callback()
        
        @self.sio.event
        def disconnect():
            self.connected = False
            logger.info("🔌 Desconectado do servidor WebSocket.")
            
            if self.on_disconnected_callback:
                self.on_disconnected_callback()
        
        @self.sio.event
        def comando(data):
            """Recebe comandos do servidor"""
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
        
        # Inicia thread dedicada de conexão/monitoramento para não bloquear main thread
        connect_thread = threading.Thread(target=self._connection_loop, daemon=True, name="WebSocketConnectionLoop")
        connect_thread.start()
        return True

    def _connection_loop(self):
        """Loop eterno de conexão e reconexão"""
        logger.info(f"🔄 Iniciando loop de conexão WebSocket com {self.server_url}")
        
        while True:
            if not self.connected:
                try:
                    # Força desconexão prévia se houver estado inconsistente
                    if self.sio.connected:
                        self.sio.disconnect()
                        
                    self.sio.connect(self.server_url, wait_timeout=CONNECTION_TIMEOUT)
                    # O evento 'connect' irá setar self.connected = True e resetar delays
                except Exception as e:
                    logger.error(f"❌ Falha na conexão WebSocket: {e}")
                    logger.info(f"⏳ Tentando novamente em {self.reconnection_delay} segundos...")
                    time.sleep(self.reconnection_delay)
                    # Backoff exponencial simples até MAX_RECONNECTION_DELAY
                    self.reconnection_delay = min(self.reconnection_delay * 1.5, MAX_RECONNECTION_DELAY)
            else:
                # Se já está conectado, apenas dorme e verifica novamente depois
                time.sleep(5)
    
    def disconnect(self):
        """Desconecta do servidor"""
        try:
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
        """Inicia thread de heartbeat (agora apenas monitora, já que o sio tem ping/pong interno)"""
        # O Socket.IO já possui mecanismo de Ping/Pong interno.
        # Vamos manter apenas um log periódico de saúde se necessário, mas sem flood.
        pass
    
    def is_connected(self) -> bool:
        """Retorna se está conectado"""
        return self.connected and self.sio.connected