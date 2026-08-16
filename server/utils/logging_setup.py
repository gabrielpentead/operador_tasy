#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sistema de logging avançado para o servidor Painel de Senhas HSV
"""

import os
import sys
import json
import logging
import logging.handlers
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

class JSONFormatter(logging.Formatter):
    """Formatter para logs estruturados em JSON"""
    
    def format(self, record):
        log_entry = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'thread': record.threadName,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Adicionar informações de exceção se houver
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        # Adicionar campos extras se houver
        if hasattr(record, 'extra_data'):
            log_entry.update(record.extra_data)
        
        return json.dumps(log_entry, ensure_ascii=False)

class ColoredFormatter(logging.Formatter):
    """Formatter com cores para terminal"""
    
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
        'RESET': '\033[0m'      # Reset
    }
    
    def format(self, record):
        log_color = self.COLORS.get(record.levelname, '')
        reset_color = self.COLORS['RESET']
        
        # Aplicar cor apenas ao nível do log
        record.levelname = f"{log_color}{record.levelname}{reset_color}"
        
        return super().format(record)

def setup_logging(config) -> logging.Logger:
    """
    Configura o sistema de logging avançado
    
    Args:
        config: Objeto de configuração com atributos de logging
        
    Returns:
        Logger configurado
    """
    try:
        # Criar diretório de logs se não existir
        log_file_path = Path(config.logging.file_path)
        log_file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Configurar logger raiz
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, config.logging.level.upper()))
        
        # Remover handlers existentes para evitar duplicação
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Handler para console com cores (apenas em desenvolvimento)
        console_handler = logging.StreamHandler(sys.stdout)
        if config.is_development():
            console_formatter = ColoredFormatter(
                '%(asctime)s - %(name)s - %(levelname)s - [%(threadName)s] - %(message)s',
                datefmt='%H:%M:%S'
            )
        else:
            console_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(logging.INFO)
        root_logger.addHandler(console_handler)
        
        # Handler para arquivo com rotação
        if config.logging.file_enabled:
            file_handler = logging.handlers.RotatingFileHandler(
                log_file_path,
                maxBytes=config.logging.max_bytes,
                backupCount=config.logging.backup_count,
                encoding='utf-8'
            )
            
            # Usar JSON em produção, texto em desenvolvimento
            if config.is_production():
                file_formatter = JSONFormatter()
            else:
                file_formatter = logging.Formatter(
                    config.logging.format,
                    datefmt='%Y-%m-%d %H:%M:%S'
                )
            
            file_handler.setFormatter(file_formatter)
            file_handler.setLevel(getattr(logging, config.logging.level.upper()))
            root_logger.addHandler(file_handler)
        
        # Configurar níveis de logging para bibliotecas externas
        external_loggers = {
            'urllib3': logging.WARNING,
            'werkzeug': logging.WARNING,
            'socketio': logging.INFO,
            'engineio': logging.WARNING,
            'flask': logging.INFO
        }
        
        for logger_name, level in external_loggers.items():
            logging.getLogger(logger_name).setLevel(level)
        
        # Criar logger específico para o servidor
        server_logger = logging.getLogger("TasyServerCentral")
        server_logger.info("Sistema de logging configurado com sucesso")
        server_logger.info(f"Nível: {config.logging.level}")
        server_logger.info(f"Arquivo: {log_file_path if config.logging.file_enabled else 'Desabilitado'}")
        server_logger.info(f"Ambiente: {config.server.environment}")
        
        return server_logger
        
    except Exception as e:
        # Fallback para configuração básica em caso de erro
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('server_fallback.log', encoding='utf-8')
            ]
        )
        
        fallback_logger = logging.getLogger("TasyServerCentral")
        fallback_logger.error(f"Erro ao configurar sistema de logging avançado: {e}")
        fallback_logger.warning("Usando configuração básica de fallback")
        
        return fallback_logger

def create_audit_logger() -> logging.Logger:
    """Cria um logger específico para auditoria"""
    audit_logger = logging.getLogger("TasyServerCentral.Audit")
    
    # Handler específico para auditoria
    audit_handler = logging.handlers.RotatingFileHandler(
        'logs/audit.log',
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=10,
        encoding='utf-8'
    )
    
    # Formato específico para auditoria
    audit_formatter = JSONFormatter()
    audit_handler.setFormatter(audit_formatter)
    audit_handler.setLevel(logging.INFO)
    
    audit_logger.addHandler(audit_handler)
    audit_logger.setLevel(logging.INFO)
    
    # Não propagar para o logger raiz para evitar duplicação
    audit_logger.propagate = False
    
    return audit_logger

def log_audit_event(action: str, user_id: Optional[str] = None, details: Optional[Dict] = None):
    """
    Registra um evento de auditoria
    
    Args:
        action: Ação realizada
        user_id: ID do usuário (operador)
        details: Detalhes adicionais
    """
    audit_logger = logging.getLogger("TasyServerCentral.Audit")
    
    audit_data = {
        'action': action,
        'user_id': user_id,
        'timestamp': datetime.now().isoformat(),
        'details': details or {}
    }
    
    # Usar extra_data para incluir no JSON
    audit_logger.info(f"Audit: {action}", extra={'extra_data': audit_data})
