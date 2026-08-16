#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Módulo de configuração centralizada para o servidor Painel de Senhas HSV
"""

import os
import json
import secrets
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger("TasyServerCentral.Config")

@dataclass
class DatabaseConfig:
    """Configurações do banco de dados"""
    path: str = "data/operadores.db"
    backup_enabled: bool = True
    backup_interval_hours: int = 24

@dataclass
class SecurityConfig:
    """Configurações de segurança"""
    secret_key: str = ""
    cors_origins: list = None
    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = 60
    
    def __post_init__(self):
        if not self.secret_key:
            self.secret_key = secrets.token_hex(32)
        if self.cors_origins is None:
            self.cors_origins = [
                "http://localhost:*", 
                "http://127.0.0.1:*",
                "http://172.16.28.95:*",
                "*"  # Temporário para desenvolvimento
            ]

@dataclass
class ServerConfig:
    """Configurações do servidor"""
    host: str = "172.16.28.95"
    port: int = 5000
    debug: bool = False
    environment: str = "production"
    workers: int = 1

@dataclass
class HealthConfig:
    """Limites para classificação de saúde dos operadores"""
    # Nível Atenção
    atencao_ram: float = 85.0
    atencao_disco: float = 85.0
    atencao_temperatura: float = 75.0
    # Nível Crítico
    critico_ram: float = 95.0
    critico_disco: float = 95.0
    critico_temperatura: float = 85.0
    # Tempo sem comunicação (minutos) para considerar crítico
    sem_comunicacao_minutos: int = 5

@dataclass
class LoggingConfig:
    """Configurações de logging"""
    level: str = "INFO"
    file_enabled: bool = True
    file_path: str = "logs/server.log"
    max_bytes: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5
    format: str = "%(asctime)s - %(name)s - %(levelname)s - [%(threadName)s] - %(message)s"

class Config:
    """Classe principal de configuração do sistema"""
    
    def __init__(self, config_file: str = "data/server_config.json", env_file: str = ".env"):
        self.config_file = Path(config_file)
        self.env_file = Path(env_file)
        
        # Configurações padrão
        self.database = DatabaseConfig()
        self.security = SecurityConfig()
        self.server = ServerConfig()
        self.logging = LoggingConfig()
        self.health = HealthConfig()
        
        # Carregar configurações
        self._load_from_env()
        self._load_from_file()
        self._ensure_directories()
    
    def _load_from_env(self):
        """Carrega configurações de variáveis de ambiente"""
        # Servidor
        self.server.host = os.getenv("TASY_HOST", self.server.host)
        self.server.port = int(os.getenv("TASY_PORT", self.server.port))
        self.server.debug = os.getenv("TASY_DEBUG", "false").lower() == "true"
        self.server.environment = os.getenv("TASY_ENV", self.server.environment)
        
        # Segurança
        if os.getenv("TASY_SECRET_KEY"):
            self.security.secret_key = os.getenv("TASY_SECRET_KEY")
        
        cors_origins = os.getenv("TASY_CORS_ORIGINS")
        if cors_origins:
            self.security.cors_origins = cors_origins.split(",")
        
        # Logging
        self.logging.level = os.getenv("TASY_LOG_LEVEL", self.logging.level)
        self.logging.file_path = os.getenv("TASY_LOG_FILE", self.logging.file_path)
        
        # Database
        self.database.path = os.getenv("TASY_DB_PATH", self.database.path)
    
    def _load_from_file(self):
        """Carrega configurações do arquivo JSON"""
        if not self.config_file.exists():
            logger.info(f"Arquivo de configuração não encontrado: {self.config_file}")
            self._save_to_file()
            return
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Atualizar configurações com dados do arquivo
            if 'server' in data:
                server_data = data['server']
                self.server.host = server_data.get('host', self.server.host)
                self.server.port = server_data.get('port', self.server.port)
                self.server.debug = server_data.get('debug', self.server.debug)
                self.server.environment = server_data.get('environment', self.server.environment)
            
            if 'security' in data:
                security_data = data['security']
                if 'secret_key' in security_data and security_data['secret_key']:
                    self.security.secret_key = security_data['secret_key']
                if 'cors_origins' in security_data:
                    self.security.cors_origins = security_data['cors_origins']
            
            if 'logging' in data:
                logging_data = data['logging']
                self.logging.level = logging_data.get('level', self.logging.level)
                self.logging.file_path = logging_data.get('file_path', self.logging.file_path)
            
            if 'database' in data:
                db_data = data['database']
                self.database.path = db_data.get('path', self.database.path)
                self.database.backup_enabled = db_data.get('backup_enabled', self.database.backup_enabled)
            
            logger.info(f"Configurações carregadas de: {self.config_file}")
            
        except Exception as e:
            logger.error(f"Erro ao carregar configurações: {e}")
            logger.info("Usando configurações padrão")
    
    def _save_to_file(self):
        """Salva configurações no arquivo JSON"""
        try:
            # Criar diretório se não existir
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                'server': asdict(self.server),
                'security': {
                    'secret_key': self.security.secret_key,
                    'cors_origins': self.security.cors_origins,
                    'rate_limit_enabled': self.security.rate_limit_enabled,
                    'rate_limit_per_minute': self.security.rate_limit_per_minute
                },
                'logging': asdict(self.logging),
                'database': asdict(self.database)
            }
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Configurações salvas em: {self.config_file}")
            
        except Exception as e:
            logger.error(f"Erro ao salvar configurações: {e}")
    
    def _ensure_directories(self):
        """Garante que os diretórios necessários existam"""
        directories = [
            Path(self.database.path).parent,
            Path(self.logging.file_path).parent,
            Path("static"),
            Path("templates")
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    def update_server_config(self, host: str, port: int) -> bool:
        """Atualiza configurações do servidor"""
        try:
            # Validar entrada
            if not host or not isinstance(port, int) or port < 1024 or port > 65535:
                raise ValueError("Host ou porta inválidos")
            
            self.server.host = host
            self.server.port = port
            self._save_to_file()
            
            logger.info(f"Configurações do servidor atualizadas: {host}:{port}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao atualizar configurações do servidor: {e}")
            return False
    
    def get_flask_config(self) -> Dict[str, Any]:
        """Retorna configurações formatadas para Flask"""
        return {
            'SECRET_KEY': self.security.secret_key,
            'DEBUG': self.server.debug,
            'ENV': self.server.environment,
            'TESTING': False
        }
    
    def get_cors_config(self) -> Dict[str, Any]:
        """Retorna configurações do CORS"""
        if self.server.environment == "development":
            return {"origins": "*"}
        else:
            # Incluir o próprio host do servidor nas origens aceitas
            origins = list(self.security.cors_origins)
            server_origin = f"http://{self.server.host}:{self.server.port}"
            if server_origin not in origins:
                origins.append(server_origin)
            return {"origins": origins}
    
    def is_development(self) -> bool:
        """Verifica se está em modo de desenvolvimento"""
        return self.server.environment == "development" or self.server.debug
    
    def is_production(self) -> bool:
        """Verifica se está em modo de produção"""
        return self.server.environment == "production" and not self.server.debug

# Instância global da configuração
config = Config()
