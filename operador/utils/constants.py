#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Constantes utilizadas em todo o Cliente Operador Tasy
"""

import socket
import platform

# === INFORMAÇÕES DO SISTEMA ===
VERSION = "1.5.8"
HOSTNAME = socket.gethostname()
SYSTEM_INFO = f"{platform.system()} {platform.release()}"

# === CONFIGURAÇÕES DO SERVIDOR ===
DEFAULT_SERVER_HOST = "172.16.28.95"
DEFAULT_SERVER_PORT = 5000
DEFAULT_SERVER_URL = f"http://{DEFAULT_SERVER_HOST}:{DEFAULT_SERVER_PORT}"
DEFAULT_SERVER_TIMEOUT = 15

# === CONFIGURAÇÕES DE CONEXÃO ===
HEARTBEAT_INTERVAL = 25
RECONNECTION_DELAY = 5
MAX_RECONNECTION_DELAY = 60
CONNECTION_TIMEOUT = 20

# Heartbeat de aplicação (evento 'heartbeat' já existente no servidor). Serve
# de sinal de vida acima do ping/pong do engine.io: se o 'heartbeat_ack' parar
# de chegar, o watchdog identifica uma conexão "muda" (zumbi) e força a
# reconexão — sem reiniciar o operador.
APP_HEARTBEAT_INTERVAL = 15        # de quanto em quanto tempo mandar o heartbeat
WATCHDOG_CHECK_INTERVAL = 10       # de quanto em quanto tempo o watchdog verifica
WATCHDOG_SILENCE_LIMIT = 45        # silêncio máximo tolerado antes de forçar reconexão

# === STATUS DO OPERADOR ===
STATUS_DISCONNECTED = "desconectado"
STATUS_CONNECTED = "conectado"
STATUS_AUTOMATION_RUNNING = "executando"
STATUS_AUTOMATION_STOPPED = "parado"
STATUS_ERROR = "erro"

# === INTERVALOS DE ATUALIZAÇÃO ===
STATUS_UPDATE_INTERVAL = 5
AUTOMATION_MONITOR_INTERVAL = 5 # Intervalo para o monitor verificar a saúde das automações

# === COMANDOS VÁLIDOS ===
VALID_COMMANDS = ["iniciar", "parar", "reiniciar", "status"]

# === TIPOS DE CADASTRO E AUTOMAÇÃO ===
CADASTRO_MONITOR = 'Monitor de Senhas'
CADASTRO_TOTEM = 'Totem de Senhas'
CADASTRO_AMBOS = 'Ambos'

TARGET_MONITOR = 'monitor'
TARGET_TOTEM = 'totem'
TARGET_AMBOS = 'ambos'

AUTOMATION_PORT_MONITOR = 9222
AUTOMATION_PORT_TOTEM = 9223

# === CONFIGURAÇÕES DE AUTOMAÇÃO ===
ERROR_CHECK_INTERVAL = 5 # 5 segundos para detecção rápida
BROWSER_STARTUP_WAIT = 7

# Tempo máximo (s) que uma recuperação/reinício tem para chegar ao estado
# OPERACIONAL (Tasy carregado e monitor ativado). Serve para medir o RTO e o
# resultado (sucesso/falha) do reinício pelo estado REAL do painel, e não por um
# retrato prematuro logo após subir a thread.
RTO_TIMEOUT_S = 120
RTO_POLL_S = 1

# === SELETORES TASY ===
# (Adicionar seletores comuns aqui para facilitar manutenção)
USER_FIELD_ID = "loginUsername"
PASS_FIELD_ID = "loginPassword"
LOGIN_BUTTON_CSS = "input.btn-green.w-login-button"

# === CONFIGURAÇÕES DE LOG ===
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - [%(threadName)s] - %(message)s"
LOG_MAX_BYTES = 10 * 1024 * 1024  # 10MB
LOG_BACKUP_COUNT = 5

# === CONFIGURAÇÕES DE CRIPTOGRAFIA ===
CRYPTO_PREFIX = "encrypted:"
