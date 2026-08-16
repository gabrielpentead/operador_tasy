#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Módulo de criptografia para senhas do Cliente Operador Tasy
"""

import base64
import socket
import logging
from typing import Optional

logger = logging.getLogger("TasyOperador.Crypto")

class CryptoManager:
    """Gerenciador de criptografia simples usando hostname como chave"""
    
    def __init__(self):
        self.hostname = socket.gethostname()
        self.key = self._generate_key()
    
    def _generate_key(self) -> bytes:
        """Gera chave baseada no hostname"""
        return self.hostname.encode('utf-8')
    
    def _xor_encrypt_decrypt(self, data: bytes, key: bytes) -> bytes:
        """Aplica XOR entre dados e chave"""
        key_len = len(key)
        return bytes(data[i] ^ key[i % key_len] for i in range(len(data)))
    
    def encrypt_password(self, password: str) -> str:
        """Criptografa uma senha"""
        try:
            if not password:
                return ""
            
            password_bytes = password.encode('utf-8')
            encrypted_bytes = self._xor_encrypt_decrypt(password_bytes, self.key)
            encrypted_b64 = base64.b64encode(encrypted_bytes).decode('utf-8')
            
            logger.debug(f"Senha criptografada para hostname: {self.hostname}")
            return encrypted_b64
            
        except Exception as e:
            logger.error(f"Erro ao criptografar senha: {e}")
            return password  # Retorna original em caso de erro
    
    def decrypt_password(self, encrypted_password: str) -> str:
        """Descriptografa uma senha"""
        try:
            if not encrypted_password:
                return ""
            
            encrypted_bytes = base64.b64decode(encrypted_password.encode('utf-8'))
            decrypted_bytes = self._xor_encrypt_decrypt(encrypted_bytes, self.key)
            decrypted_password = decrypted_bytes.decode('utf-8')
            
            logger.debug(f"Senha descriptografada para hostname: {self.hostname}")
            return decrypted_password
            
        except Exception as e:
            logger.error(f"Erro ao descriptografar senha: {e}")
            return encrypted_password  # Retorna original em caso de erro

# Instância global
crypto = CryptoManager()

# Funções de conveniência
def encrypt_password(password: str) -> str:
    """Criptografa uma senha usando a instância global"""
    return crypto.encrypt_password(password)

def decrypt_password(encrypted_password: str) -> str:
    """Descriptografa uma senha usando a instância global"""
    return crypto.decrypt_password(encrypted_password)
