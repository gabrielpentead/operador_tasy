#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Configuração de logging para o Cliente Operador Tasy
"""

import sys
import os
import logging
import logging.handlers
from pathlib import Path
from typing import Optional

from utils.constants import LOG_MAX_BYTES, LOG_BACKUP_COUNT, LOG_FORMAT

def get_application_path() -> str:
    """Retorna o caminho base da aplicação"""
    if getattr(sys, 'frozen', False):
        # Executando como aplicativo compilado
        return os.path.dirname(sys.executable)
    else:
        # Executando como script Python
        return os.path.dirname(os.path.abspath(__file__))

def configure_basic_logging() -> logging.Logger:
    """Configura logging básico para inicialização"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
    return logging.getLogger("TasyOperador.Init")

def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configura sistema de logging completo"""
    
    # Converter string para nível
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    # Caminho para logs
    app_path = get_application_path()
    log_dir = Path(app_path) / "logs"
    log_dir.mkdir(exist_ok=True)
    
    log_file = log_dir / "operador.log"
    
    # Configurar logger principal
    logger = logging.getLogger("TasyOperador")
    logger.setLevel(numeric_level)
    
    # Remover handlers existentes
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Handler para arquivo com rotação
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding='utf-8'
    )
    file_handler.setLevel(numeric_level)
    file_formatter = logging.Formatter(LOG_FORMAT)
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    # Handler para console (Agora usando TextualLogHandler via ConsoleUI)
    from core.console_ui import console_ui, TextualLogHandler
    # Removendo StreamHandler padrão para evitar duplicação no console
    
    # Handler customizado que atualiza a UI
    rich_ui_handler = TextualLogHandler(console_ui)
    rich_ui_handler.setLevel(numeric_level)
    rich_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt="%H:%M:%S")
    rich_ui_handler.setFormatter(rich_formatter)
    logger.addHandler(rich_ui_handler)
    
    # Configurar loggers de terceiros
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("selenium").setLevel(logging.WARNING)
    logging.getLogger("socketio").setLevel(logging.WARNING)
    logging.getLogger("engineio").setLevel(logging.WARNING)
    
    # Não propagar para o logger raiz para evitar logs duplicados
    logger.propagate = False
    
    logger.info(f"Sistema de logging completo inicializado")
    logger.info(f"Nível: {level}")
    logger.info(f"Arquivo: {log_file}")
    
    return logger
