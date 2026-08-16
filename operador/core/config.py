#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gerenciamento de configurações do Cliente Operador Tasy
"""

import os
import sys
import configparser
from pathlib import Path
from typing import Tuple, Optional
import logging

from core.crypto import crypto
from utils.constants import (
    DEFAULT_SERVER_HOST, DEFAULT_SERVER_PORT, HOSTNAME, CRYPTO_PREFIX
)

logger = logging.getLogger("TasyOperador.Config")

class OperadorConfig:
    """Gerenciador de configurações do operador"""
    
    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file or self._get_default_config_path()
        self.config = configparser.ConfigParser()
        self._ensure_config_file()
        self.load_config()
    
    def _get_default_config_path(self) -> str:
        base_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_dir, "config.ini")
    
    def _ensure_config_file(self):
        if not os.path.exists(self.config_file):
            logger.info("Criando arquivo de configuração padrão")
            self._create_default_config()
    
    def _create_default_config(self):
        config = configparser.ConfigParser()
        config.add_section('operador')
        config.set('operador', 'id', '')
        config.set('operador', 'nome', f'Operador-{HOSTNAME}')
        config.set('operador', 'tipo_cadastro', 'Monitor de Senhas')
        config.set('operador', 'usa_credenciais_separadas', 'false')

        config.add_section('servidor')
        config.set('servidor', 'host', DEFAULT_SERVER_HOST)
        config.set('servidor', 'porta', str(DEFAULT_SERVER_PORT))
        config.set('servidor', 'tasy_url', 'https://tasy.hospitalsaovicente.org.br/#/')
        
        config.add_section('tasy_compartilhado')
        config.set('tasy_compartilhado', 'username', '')
        config.set('tasy_compartilhado', 'senha', '')

        config.add_section('tasy_monitor')
        config.set('tasy_monitor', 'username', '')
        config.set('tasy_monitor', 'senha', '')

        config.add_section('tasy_totem')
        config.set('tasy_totem', 'username', '')
        config.set('tasy_totem', 'senha', '')
        
        config.add_section('sistema')
        config.set('sistema', 'debug', 'false')
        config.set('sistema', 'auto_start', 'true')
        config.set('sistema', 'edgedriver_version', '')
        config.set('sistema', 'log_level', 'INFO')

        # Sobrescrita manual de monitores. Vazio = decisão automática pelo
        # tamanho físico das telas. Preencher com o número do DISPLAY do
        # Windows (1, 2, ...) apenas em máquinas onde a regra automática errar.
        config.add_section('monitores')
        config.set('monitores', 'totem', '')
        config.set('monitores', 'painel', '')

        with open(self.config_file, 'w', encoding='utf-8') as f:
            config.write(f)
        logger.info(f"Configuração padrão criada em: {self.config_file}")
    
    def load_config(self):
        try:
            self.config.read(self.config_file, encoding='utf-8')
            logger.debug(f"Configuração carregada de: {self.config_file}")
        except Exception as e:
            logger.error(f"Erro ao carregar configuração: {e}")
            self._create_default_config()
            self.config.read(self.config_file, encoding='utf-8')
    
    def save_config(self):
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                self.config.write(f)
            logger.debug(f"Configuração salva em: {self.config_file}")
        except Exception as e:
            logger.error(f"Erro ao salvar configuração: {e}")

    def get_config_dict(self) -> dict:
        """Retorna a configuração como um dicionário."""
        config_dict = {s: dict(self.config.items(s)) for s in self.config.sections()}
        return config_dict

    def update_from_dict(self, data: dict):
        """Atualiza a configuração a partir de um dicionário (geralmente do servidor)."""
        self.set_operator_id(data.get('id', self.get_operator_id()))
        self.set_operator_name(data.get('nome', self.get_operator_name()))
        self.set_tipo_cadastro(data.get('tipo_cadastro', self.get_tipo_cadastro()))
        self.set_usa_credenciais_separadas(data.get('usa_credenciais_separadas', self.get_usa_credenciais_separadas()))

        # Atualiza todas as credenciais
        self.set_credentials('tasy_compartilhado', data.get('username'), data.get('password'))
        self.set_credentials('tasy_monitor', data.get('username_monitor'), data.get('password_monitor'))
        self.set_credentials('tasy_totem', data.get('username_totem'), data.get('password_totem'))
        
        self.save_config()

    # === OPERADOR ===
    def get_operator_id(self) -> str:
        return self.config.get('operador', 'id', fallback='')
    
    def set_operator_id(self, operator_id: str):
        self.config.set('operador', 'id', operator_id)
    
    def get_operator_name(self) -> str:
        return self.config.get('operador', 'nome', fallback=f'Operador-{HOSTNAME}')
    
    def set_operator_name(self, name: str):
        self.config.set('operador', 'nome', name)

    def get_tipo_cadastro(self) -> str:
        return self.config.get('operador', 'tipo_cadastro', fallback='Monitor de Senhas')

    def set_tipo_cadastro(self, tipo: str):
        self.config.set('operador', 'tipo_cadastro', tipo)

    def get_usa_credenciais_separadas(self) -> bool:
        return self.config.getboolean('operador', 'usa_credenciais_separadas', fallback=False)

    def set_usa_credenciais_separadas(self, value: bool):
        self.config.set('operador', 'usa_credenciais_separadas', str(value).lower())
    
    # === SERVIDOR ===
    def get_server_url(self) -> str:
        host = self.config.get('servidor', 'host', fallback=DEFAULT_SERVER_HOST)
        port = self.config.getint('servidor', 'porta', fallback=DEFAULT_SERVER_PORT)
        return f"http://{host}:{port}"

    def get_tasy_url(self) -> str:
        return self.config.get('servidor', 'tasy_url', fallback='https://tasy.hospitalsaovicente.org.br/#/')
    
    # === CREDENCIAIS TASY ===
    def get_credentials(self, section: str) -> Tuple[str, str, str]:
        """Função genérica para obter credenciais de uma seção."""
        if not self.config.has_section(section):
            return '', '', ''
        
        usuario = self.config.get(section, 'usuario', fallback='')
        senha_encrypted = self.config.get(section, 'senha', fallback='')
        
        senha = crypto.decrypt_password(senha_encrypted[len(CRYPTO_PREFIX):]) if senha_encrypted.startswith(CRYPTO_PREFIX) else senha_encrypted
        return usuario, senha, "" # Mantendo o terceiro retorno como string vazia para compatibilidade

    def set_credentials(self, section: str, usuario: Optional[str], senha: Optional[str]):
        """Função genérica para definir credenciais em uma seção."""
        if not self.config.has_section(section):
            self.config.add_section(section)
        
        if usuario is not None: self.config.set(section, 'usuario', usuario)
        if senha is not None: 
            senha_encrypted = CRYPTO_PREFIX + crypto.encrypt_password(senha)
            self.config.set(section, 'senha', senha_encrypted)

    def has_any_credentials(self) -> bool:
        """Verifica se existe qualquer conjunto de credenciais preenchido."""
        if self.get_usa_credenciais_separadas():
            u_mon, _, _ = self.get_credentials('tasy_monitor')
            u_tot, _, _ = self.get_credentials('tasy_totem')
            return bool(u_mon and u_tot)
        else:
            u, _, _ = self.get_credentials('tasy_compartilhado')
            return bool(u)

    # === SISTEMA ===
    def get_system_config(self) -> dict:
        return {
            'debug': self.config.getboolean('sistema', 'debug', fallback=False),
            'auto_start': self.config.getboolean('sistema', 'auto_start', fallback=False),
            'edgedriver_version': self.config.get('sistema', 'edgedriver_version', fallback='')
        }

    # === MONITORES ===
    def get_monitor_preference(self, alvo: str) -> Optional[int]:
        """Número do DISPLAY fixado manualmente para 'totem' ou 'painel'.

        Devolve None quando não configurado — aí vale a decisão automática pelo
        tamanho físico das telas. Instalações antigas não têm a seção
        [monitores]; o fallback do configparser cobre esse caso sem quebrar,
        então nenhuma migração de config.ini é necessária.
        """
        try:
            valor = (self.config.get('monitores', alvo, fallback='') or '').strip()
            return int(valor) if valor else None
        except Exception:
            return None

    def set_edgedriver_version(self, version: str):
        """Salva a versão atual do EdgeDriver instalado."""
        if not self.config.has_section('sistema'):
            self.config.add_section('sistema')
        self.config.set('sistema', 'edgedriver_version', version)
        self.save_config()

    def get_log_level(self) -> str:
        """Retorna o nível de log configurado (padrão: INFO)"""
        if self.config.getboolean('sistema', 'debug', fallback=False):
            return "DEBUG"
        return self.config.get('sistema', 'log_level', fallback='INFO')
