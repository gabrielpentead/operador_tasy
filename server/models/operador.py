#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Modelo de dados para Operador
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict
import uuid

@dataclass
class Operador:
    """Modelo de dados para um operador do sistema"""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    nome: str = ""
    descricao: Optional[str] = None
    username: str = ""
    password: str = ""
    data_criacao: str = field(default_factory=lambda: datetime.now().isoformat())
    data_atualizacao: str = field(default_factory=lambda: datetime.now().isoformat())
    
    # Campos de runtime (não salvos no banco)
    online: bool = field(default=False, init=False)
    status: str = field(default="Desconectado", init=False)
    ultima_comunicacao: Optional[str] = field(default=None, init=False)
    ip: Optional[str] = field(default="N/A", init=False)
    hostname: Optional[str] = field(default="N/A", init=False)
    sistema_operacional: Optional[str] = field(default=None, init=False)
    
    def to_dict(self, include_runtime: bool = True) -> Dict:
        """Converte para dicionário"""
        data = {
            'id': self.id,
            'nome': self.nome,
            'descricao': self.descricao,
            'username': self.username,
            'password': self.password,
            'data_criacao': self.data_criacao,
            'data_atualizacao': self.data_atualizacao,
            
            # Campos persistidos de última conexão conhecida
            'last_ip': getattr(self, 'last_ip', None),
            'last_hostname': getattr(self, 'last_hostname', None),
            'last_os': getattr(self, 'last_os', None)
        }
        
        if include_runtime:
            # Se estiver online, usa os dados em tempo real
            # Se offline, usa os últimos conhecidos (persistidos ou padrão)
            current_ip = self.ip if self.online else (getattr(self, 'last_ip', 'N/A'))
            current_hostname = self.hostname if self.online else (getattr(self, 'last_hostname', 'N/A'))
            current_os = self.sistema_operacional if self.online else (getattr(self, 'last_os', 'N/A'))

            data.update({
                'online': self.online,
                'status': self.status,
                'ultima_comunicacao': self.ultima_comunicacao,
                'ip': current_ip,
                'hostname': current_hostname,
                'sistema_operacional': current_os
            })
        
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Operador':
        """Cria instância a partir de dicionário"""
        # Filtrar apenas campos que existem no dataclass
        valid_fields = {
            'id', 'nome', 'descricao', 'username', 'password', 
            'data_criacao', 'data_atualizacao'
        }
        
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        operador = cls(**filtered_data)
        
        # Carregar campos persistidos de última conexão se existirem no dicionário (banco)
        if 'last_ip' in data: setattr(operador, 'last_ip', data['last_ip'])
        if 'last_hostname' in data: setattr(operador, 'last_hostname', data['last_hostname'])
        if 'last_os' in data: setattr(operador, 'last_os', data['last_os'])
        
        # Definir campos de runtime se presentes
        if 'online' in data:
            operador.online = data['online']
        if 'status' in data:
            operador.status = data['status']
        if 'ultima_comunicacao' in data:
            operador.ultima_comunicacao = data['ultima_comunicacao']
        if 'ip' in data:
            operador.ip = data['ip']
        if 'hostname' in data:
            operador.hostname = data['hostname']
        if 'sistema_operacional' in data:
            operador.sistema_operacional = data['sistema_operacional']
        
        return operador
    
    def update_timestamp(self):
        """Atualiza timestamp de modificação"""
        self.data_atualizacao = datetime.now().isoformat()
    
    def is_credentials_complete(self) -> bool:
        """Verifica se as credenciais estão completas"""
        return bool(self.username and self.password)
    
    def get_display_name(self) -> str:
        """Retorna nome para exibição"""
        return self.nome or f"Operador-{self.id[:8]}"

@dataclass
class LogEntry:
    """Modelo para entrada de log"""
    
    id: int = 0
    operador_id: Optional[str] = None
    acao: str = ""
    detalhes: str = ""
    data: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict:
        """Converte para dicionário"""
        return {
            'id': self.id,
            'operador_id': self.operador_id,
            'acao': self.acao,
            'detalhes': self.detalhes,
            'data': self.data
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'LogEntry':
        """Cria instância a partir de dicionário"""
        return cls(
            id=data.get('id', 0),
            operador_id=data.get('operador_id'),
            acao=data.get('acao', ''),
            detalhes=data.get('detalhes', ''),
            data=data.get('data', datetime.now().isoformat())
        )
