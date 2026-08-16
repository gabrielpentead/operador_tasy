#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cliente para comunicação com API REST do servidor
"""

import requests
import logging
from typing import Dict, Tuple, Optional, Any
import getpass

from utils.constants import DEFAULT_SERVER_TIMEOUT, HOSTNAME

logger = logging.getLogger("TasyOperador.ServerAPI")

class ServerAPI:
    """Cliente para comunicação com API REST do servidor"""
    
    def __init__(self, base_url: str, timeout: int = DEFAULT_SERVER_TIMEOUT):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': f'TasyOperador/{HOSTNAME}'
        })
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Tuple[bool, Optional[Dict], Optional[str]]:
        url = f"{self.base_url}{endpoint}"
        try:
            response = self.session.request(method=method, url=url, timeout=self.timeout, **kwargs)
            if 200 <= response.status_code < 300:
                return True, response.json() if response.content else {'message': 'OK'}, None
            else:
                return False, None, f"HTTP {response.status_code}: {response.text}"
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro de requisição para {url}: {e}")
            return False, None, f"Erro de conexão: {e}"
        except Exception as e:
            logger.error(f"Erro inesperado para {url}: {e}")
            return False, None, f"Erro inesperado: {e}"
    
    def test_connection(self) -> bool:
        success, _, _ = self._make_request('GET', '/health')
        return success
    
    def register_operator(self, operator_data: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[str]]:
        success, data, error = self._make_request('POST', '/api/operadores', json=operator_data)
        if success and data:
            return True, data.get('id'), data.get('message', 'Operador registrado com sucesso')
        return False, None, error or "Erro desconhecido ao registrar operador"
                
    def get_operator_credentials(self, operator_id: str) -> Tuple[bool, Optional[Dict], Optional[str]]:
        success, data, error = self._make_request('GET', f'/api/operadores/{operator_id}/credentials')
        return (True, data, None) if success and data else (False, None, error or "Erro ao obter credenciais")
    
    def interactive_registration(self) -> Tuple[bool, Optional[str], Dict[str, Any]]:
        """Registro interativo do operador"""
        print("\n" + "="*60)
        print("  🏥 REGISTRO DE OPERADOR - PAINEL DE SENHAS HSV")
        print("="*60)
        print(f"  🖥️  Hostname: {HOSTNAME}")
        print(f"  🌐 Servidor: {self.base_url}")
        print("="*60)
        
        try:
            operator_data = {}
            nome_default = f"Operador-{HOSTNAME}"
            operator_data['nome'] = input(f"Nome do operador [{nome_default}]: ").strip() or nome_default
            descricao_default = f"Operador para {HOSTNAME}"
            operator_data['descricao'] = input(f"Descrição (opcional) [{descricao_default}]: ").strip() or descricao_default

            print("\n📋 Tipo de Cadastro:")
            print("   1: Monitor de Senhas (Exibe senhas chamadas na TV)")
            print("   2: Totem de Senhas (Permite chamar senhas)")
            print("   3: Ambos (Executa o Monitor e o Totem na mesma máquina)")
            tipo_map = {'1': 'Monitor de Senhas', '2': 'Totem de Senhas', '3': 'Ambos'}
            while True:
                choice = input("Escolha o tipo [1]: ").strip() or '1'
                if choice in tipo_map:
                    operator_data['tipo_cadastro'] = tipo_map[choice]
                    break
                print("Opção inválida. Por favor, escolha 1, 2 ou 3.")

            operator_data['usa_credenciais_separadas'] = False
            if operator_data['tipo_cadastro'] == 'Ambos':
                usa_separadas_choice = input("\nDeseja usar credenciais diferentes para Monitor e Totem? (s/N): ").strip().lower()
                if usa_separadas_choice in ['s', 'sim']:
                    operator_data['usa_credenciais_separadas'] = True
                    print("\n🔑 Credenciais do Monitor (TV):")
                    operator_data['username_monitor'] = input("Usuário Tasy do Monitor: ").strip()
                    operator_data['password_monitor'] = getpass.getpass("Senha Tasy do Monitor: ").strip()

                    print("\n🔑 Credenciais do Totem (Chamada):")
                    operator_data['username_totem'] = input("Usuário Tasy do Totem: ").strip()
                    operator_data['password_totem'] = getpass.getpass("Senha Tasy do Totem: ").strip()

                    # Preenche as credenciais principais com as do monitor como fallback
                    operator_data['username'] = operator_data['username_monitor']
                    operator_data['password'] = operator_data['password_monitor']

            if not operator_data['usa_credenciais_separadas']:
                print("\n🔑 Credenciais do Tasy:")
                operator_data['username'] = input("Usuário Tasy: ").strip()
                operator_data['password'] = getpass.getpass("Senha Tasy: ").strip()
            
            print(f"\n🌐 Conectando ao servidor para registro: {self.base_url}")
            success, operator_id, message = self.register_operator(operator_data)
            
            if success:
                print(f"✅ Operador registrado com sucesso! ID: {operator_id}")
                operator_data['id'] = operator_id
                return True, operator_id, operator_data
            else:
                print(f"❌ Erro no registro: {message}")
                return False, None, {}
                
        except (KeyboardInterrupt, EOFError):
            print("\n🛑 Registro cancelado pelo usuário")
            return False, None, {}
        except Exception as e:
            print(f"\n❌ Erro durante o registro: {e}")
            return False, None, {}