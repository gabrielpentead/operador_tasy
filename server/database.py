#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# server/database.py - Gerenciamento de banco de dados para Central de Operadores

import sqlite3
import json
import os
import uuid
import logging
from datetime import datetime

logger = logging.getLogger("TasyServerCentral")

class Database:
    """
    Classe para gerenciar operações de banco de dados da Central de Operadores.
    Utiliza SQLite como armazenamento para simplicidade e portabilidade.
    """
    
    def __init__(self, db_path='data/operadores.db'):
        """Inicializa a conexão com o banco de dados e cria as tabelas se não existirem"""
        self.db_path = db_path
        self._ensure_dir_exists()
        self.conn = self._connect()
        self._create_tables()
        self._verificar_migracao()
    
    def _ensure_dir_exists(self):
        """Garante que o diretório para o banco de dados existe"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
    
    def _connect(self):
        """Cria uma conexão com o banco de dados SQLite"""
        try:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.Error as e:
            logger.error(f"Erro ao conectar ao banco de dados: {str(e)}")
            raise
    
    def _create_tables(self):
        """Cria as tabelas necessárias se não existirem"""
        try:
            cursor = self.conn.cursor()
            
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS operadores (
                id TEXT PRIMARY KEY,
                nome TEXT NOT NULL,
                descricao TEXT,
                tipo_cadastro TEXT DEFAULT 'Monitor de Senhas',
                data_criacao TEXT,
                data_atualizacao TEXT,

                -- Credenciais principais/compartilhadas
                username TEXT NOT NULL,
                password TEXT NOT NULL,

                -- Flag para credenciais separadas
                usa_credenciais_separadas BOOLEAN DEFAULT FALSE,

                -- Credenciais do Monitor
                username_monitor TEXT,
                password_monitor TEXT,

                -- Credenciais do Totem
                username_totem TEXT,
                password_totem TEXT
            )
            ''')
            
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operador_id TEXT,
                acao TEXT NOT NULL,
                detalhes TEXT,
                data TEXT,
                FOREIGN KEY (operador_id) REFERENCES operadores (id)
            )
            ''')
            
            self.conn.commit()
            logger.info("Tabelas do banco de dados verificadas e criadas se necessário")
        except sqlite3.Error as e:
            logger.error(f"Erro ao criar tabelas: {str(e)}")
            raise
    
    def _verificar_migracao(self):
        """Verifica se há necessidade de migração para adicionar colunas faltantes"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("PRAGMA table_info(operadores)")
            colunas = [col[1] for col in cursor.fetchall()]
            
            migracoes = {
                'tipo_cadastro': "ADD COLUMN tipo_cadastro TEXT DEFAULT 'Monitor de Senhas'",
                'usa_credenciais_separadas': "ADD COLUMN usa_credenciais_separadas BOOLEAN DEFAULT FALSE",
                'username_monitor': "ADD COLUMN username_monitor TEXT",
                'password_monitor': "ADD COLUMN password_monitor TEXT",
                'username_totem': "ADD COLUMN username_totem TEXT",
                'password_totem': "ADD COLUMN password_totem TEXT",
                'deleted': "ADD COLUMN deleted BOOLEAN DEFAULT FALSE",
                'last_ip': "ADD COLUMN last_ip TEXT",
                'last_hostname': "ADD COLUMN last_hostname TEXT",
                'last_os': "ADD COLUMN last_os TEXT"
            }

            for coluna, definicao in migracoes.items():
                if coluna not in colunas:
                    logger.info(f"Migrando tabela: adicionando coluna '{coluna}' à tabela 'operadores'")
                    cursor.execute(f"ALTER TABLE operadores {definicao}")
                    self.conn.commit()
                    logger.info(f"Migração da coluna '{coluna}' concluída com sucesso")
                
        except sqlite3.Error as e:
            logger.error(f"Erro ao verificar/realizar migração: {str(e)}")
            raise
    
    def add_operador(self, data):
        """Adiciona um novo operador ao banco de dados a partir de um dicionário, gerando UUID"""
        try:
            operador_id = str(uuid.uuid4())
            return self.add_operador_with_id(operador_id, data)
        except sqlite3.Error as e:
            logger.error(f"Erro ao adicionar operador: {str(e)}")
            raise

    def add_operador_with_id(self, operador_id, data):
        """Adiciona um novo operador com ID específico (Útil para sincronização offline -> online)"""
        try:
            cursor = self.conn.cursor()
            data_atual = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('''
            INSERT INTO operadores (
                id, nome, descricao, username, password, tipo_cadastro, 
                usa_credenciais_separadas, username_monitor, password_monitor,
                username_totem, password_totem,
                data_criacao, data_atualizacao, deleted
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, FALSE)
            ''', (
                operador_id, data.get('nome'), data.get('descricao'), data.get('username'), data.get('password'),
                data.get('tipo_cadastro'),
                data.get('usa_credenciais_separadas', False),
                data.get('username_monitor'), data.get('password_monitor'),
                data.get('username_totem'), data.get('password_totem'),
                data_atual, data_atual
            ))
            
            self.conn.commit()
            self._add_log(operador_id, "criacao", f"Operador criado com tipo: {data.get('tipo_cadastro')}")
            logger.info(f"Operador adicionado: {data.get('nome')} (ID: {operador_id})")
            return operador_id
        except sqlite3.Error as e:
            logger.error(f"Erro ao adicionar operador com ID: {str(e)}")
            raise
    
    def get_operador(self, operador_id):
        """Obtém informações de um operador específico pelo ID"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT * FROM operadores WHERE id = ?', (operador_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        except sqlite3.Error as e:
            logger.error(f"Erro ao obter operador {operador_id}: {str(e)}")
            raise
    
    def get_all_operadores(self, include_deleted=False):
        """Obtém a lista de todos os operadores cadastrados"""
        try:
            cursor = self.conn.cursor()
            if include_deleted:
                cursor.execute('SELECT * FROM operadores ORDER BY nome')
            else:
                cursor.execute('SELECT * FROM operadores WHERE deleted = FALSE OR deleted IS NULL ORDER BY nome')
            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logger.error(f"Erro ao obter lista de operadores: {str(e)}")
            raise
    
    def update_operador(self, operador_id, data):
        """Atualiza informações de um operador existente a partir de um dicionário"""
        try:
            cursor = self.conn.cursor()
            data_atual = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Constrói a query de atualização dinamicamente para não sobrescrever campos não enviados
            fields_to_update = []
            values = []
            
            for key, value in data.items():
                # Garante que apenas colunas válidas sejam atualizadas
                if key in ['nome', 'descricao', 'username', 'password', 'tipo_cadastro', 'usa_credenciais_separadas', 'username_monitor', 'password_monitor', 'username_totem', 'password_totem', 'last_ip', 'last_hostname', 'last_os']:
                    fields_to_update.append(f"{key} = ?")
                    values.append(value)
            
            if not fields_to_update:
                logger.warning(f"Nenhum campo para atualizar para o operador {operador_id}")
                return True

            fields_to_update.append("data_atualizacao = ?")
            values.extend([data_atual, operador_id])

            query = f"UPDATE operadores SET { ', '.join(fields_to_update) } WHERE id = ?"
            
            cursor.execute(query, tuple(values))
            
            self.conn.commit()
            self._add_log(operador_id, "atualizacao", "Operador atualizado")
            logger.info(f"Operador atualizado: {operador_id}")
            return True
        except sqlite3.Error as e:
            logger.error(f"Erro ao atualizar operador {operador_id}: {str(e)}")
            raise
    
    def delete_operador(self, operador_id):
        """Remove um operador do banco de dados (Soft Delete)"""
        try:
            cursor = self.conn.cursor()
            self._add_log(operador_id, "remocao", "Operador removido (Soft Delete)")
            
            # Soft delete: Marcar como deletado em vez de remover
            cursor.execute('UPDATE operadores SET deleted = TRUE WHERE id = ?', (operador_id,))
            
            self.conn.commit()
            logger.info(f"Operador marcado como deletado: {operador_id}")
            return True
        except sqlite3.Error as e:
            logger.error(f"Erro ao remover operador {operador_id}: {str(e)}")
            raise
    
    def _add_log(self, operador_id, acao, detalhes):
        """Adiciona uma entrada no log de ações"""
        try:
            cursor = self.conn.cursor()
            data_atual = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''
            INSERT INTO logs (operador_id, acao, detalhes, data)
            VALUES (?, ?, ?, ?)
            ''', (operador_id, acao, detalhes, data_atual))
            self.conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Erro ao adicionar log: {e}")
    
    def get_logs(self, operador_id=None, limit=50):
        """Obtém logs de ações, opcionalmente filtrados por operador"""
        try:
            cursor = self.conn.cursor()
            query = '''
                SELECT l.*, o.nome as operador_nome
                FROM logs l
                LEFT JOIN operadores o ON l.operador_id = o.id
                {}
                ORDER BY l.data DESC
                LIMIT ?
            '''
            params = [limit]
            where_clause = ""
            if operador_id:
                where_clause = "WHERE l.operador_id = ?"
                params.insert(0, operador_id)
            
            cursor.execute(query.format(where_clause), tuple(params))
            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logger.error(f"Erro ao obter logs: {str(e)}")
            raise
    
    def close(self):
        """Fecha a conexão com o banco de dados"""
        if self.conn:
            self.conn.close()
            logger.info("Conexão com o banco de dados fechada")
    
    def realizar_migracao(self):
        """Executa manualmente a migração do banco de dados para atualizar sua estrutura."""
        try:
            logger.info("Iniciando migração manual do banco de dados")
            self._verificar_migracao()
            logger.info("Migração do banco de dados concluída com sucesso")
            return True
        except sqlite3.Error as e:
            logger.error(f"Erro durante migração manual do banco de dados: {str(e)}")
            return False