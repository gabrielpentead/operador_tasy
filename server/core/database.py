#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# server/database.py - Gerenciamento de banco de dados para Central de Operadores

import sqlite3
import json
import os
import uuid
import logging
from datetime import datetime, timedelta

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
        self._verificar_migracao_usuarios()
        self._garantir_reinicio_padrao()
    
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
            
            # Usuários do painel administrativo. Tabela NOVA — não altera nem
            # remove nada das tabelas existentes (operadores, logs).
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                login TEXT NOT NULL UNIQUE COLLATE NOCASE,
                email TEXT COLLATE NOCASE,
                senha_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'operador',
                ativo INTEGER NOT NULL DEFAULT 1,
                data_criacao TEXT,
                data_atualizacao TEXT,
                ultimo_acesso TEXT
            )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_usuarios_login ON usuarios(login)')

            # Pedidos de redefinicao de senha.
            #
            # Guarda o HASH do token, nunca o token. Assim, mesmo quem leia o
            # banco nao consegue montar um link valido — mesma logica aplicada
            # as senhas dos usuarios.
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS redefinicoes_senha (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                criado_em TEXT NOT NULL,
                expira_em TEXT NOT NULL,
                usado_em TEXT,
                ip_solicitante TEXT,
                FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
            )
            ''')
            cursor.execute('''CREATE INDEX IF NOT EXISTS idx_redef_token
                              ON redefinicoes_senha(token_hash)''')
            cursor.execute('''CREATE INDEX IF NOT EXISTS idx_redef_usuario
                              ON redefinicoes_senha(usuario_id)''')

            # Eventos de monitoramento reportados pelo agente: reinicializações e
            # erros/ocorrências. Ficam no servidor (e não só na memória do agente)
            # para o histórico sobreviver a um reinício do próprio operador.
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS eventos_operador (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operador_id TEXT NOT NULL,
                tipo TEXT NOT NULL,          -- 'reinicio' | 'erro'
                nivel TEXT,                  -- reinicio: 'sucesso'|'falha'; erro: 'aviso'|'erro'|'critico'
                titulo TEXT,
                detalhe TEXT,
                dados_json TEXT,             -- campos extras (motivo, duracao_s, inicio, fim, ocorrencias...)
                ocorrido_em TEXT NOT NULL,   -- quando aconteceu no operador
                criado_em TEXT NOT NULL,     -- quando o servidor gravou
                FOREIGN KEY (operador_id) REFERENCES operadores (id)
            )
            ''')
            cursor.execute('''CREATE INDEX IF NOT EXISTS idx_eventos_operador
                              ON eventos_operador(operador_id, ocorrido_em)''')

            # Destinatários dos alertas críticos por e-mail (camada de
            # monitoramento de incidentes). Ficam no banco para poderem ser
            # gerenciados pela página de Configurações, sem editar código.
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS alertas_destinatarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                ativo INTEGER NOT NULL DEFAULT 1,
                recebe_critico INTEGER NOT NULL DEFAULT 1,
                data_criacao TEXT,
                data_atualizacao TEXT
            )
            ''')
            # O índice único de e-mail NÃO entra aqui: numa base que já tinha a
            # tabela, o CREATE TABLE IF NOT EXISTS não acrescenta a coluna, e o
            # índice falharia. Ele é criado em _verificar_migracao_usuarios(),
            # que roda depois e garante a coluna nos dois casos.

            # Programação dos reinícios automáticos dos painéis. Antes disso o
            # horário (06:50) era fixo; agora fica aqui para a tela de
            # Configurações gerenciar sem mexer em código. O agendador
            # (monitoring/restart_scheduler.py) só lê esta tabela.
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS reinicios_programados (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                horario TEXT NOT NULL,               -- 'HH:MM', 24h
                dias_semana TEXT NOT NULL DEFAULT '0,1,2,3,4,5,6',  -- 0=segunda..6=domingo
                target TEXT NOT NULL DEFAULT 'ambos', -- 'ambos'|'monitor'|'totem'
                descricao TEXT,
                ativo INTEGER NOT NULL DEFAULT 1,
                disparado_em TEXT,                   -- última vez que o agendador disparou
                data_criacao TEXT,
                data_atualizacao TEXT
            )
            ''')

            self.conn.commit()
            logger.info("Tabelas do banco de dados verificadas e criadas se necessário")
        except sqlite3.Error as e:
            logger.error(f"Erro ao criar tabelas: {str(e)}")
            raise
    
    def _garantir_reinicio_padrao(self):
        """Semeia o agendamento padrão (06:50, todos os dias, ambos) na primeira
        vez que a tabela `reinicios_programados` existe mas está vazia.

        Preserva o comportamento de hoje (reinício diário às 06:50) no momento
        em que essa configuração passa a ser gerenciável pela tela — sem isso,
        instalações existentes ficariam sem nenhum reinício programado até um
        admin cadastrar um manualmente.
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM reinicios_programados')
            if cursor.fetchone()[0] > 0:
                return
            agora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute(
                '''INSERT INTO reinicios_programados
                   (horario, dias_semana, target, descricao, ativo, data_criacao, data_atualizacao)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                ('06:50', '0,1,2,3,4,5,6', 'ambos', 'Reinício diário', 1, agora, agora))
            self.conn.commit()
            logger.info("Agendamento padrão de reinício (06:50, todos os dias) criado.")
        except sqlite3.Error as e:
            logger.warning(f"Não foi possível semear o agendamento padrão de reinício: {e}")

    def _verificar_migracao_usuarios(self):
        """Acrescenta colunas novas à tabela de usuários sem tocar nos dados.

        Mesmo padrão de _verificar_migracao(): confere o que já existe e só
        adiciona o que falta. Instalações que criaram a tabela antes do campo
        de e-mail ganham a coluna vazia, e os usuários seguem funcionando.
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("PRAGMA table_info(usuarios)")
            colunas = [col[1] for col in cursor.fetchall()]
            if not colunas:
                return   # tabela ainda não existe; _create_tables cuida disso

            migracoes = {
                'email': "ADD COLUMN email TEXT COLLATE NOCASE",
            }
            for coluna, definicao in migracoes.items():
                if coluna not in colunas:
                    logger.info(f"Migrando tabela: adicionando coluna '{coluna}' à tabela 'usuarios'")
                    cursor.execute(f"ALTER TABLE usuarios {definicao}")
                    self.conn.commit()
                    logger.info(f"Migração da coluna '{coluna}' concluída com sucesso")

            cursor.execute('''CREATE UNIQUE INDEX IF NOT EXISTS idx_usuarios_email
                              ON usuarios(email) WHERE email IS NOT NULL AND email != ''  ''')
            self.conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Erro na migração da tabela usuarios: {str(e)}")

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
                'last_os': "ADD COLUMN last_os TEXT",
                # Metadados de monitoramento enviados pelo agente no registro.
                # Nullable: operador que nunca reconectou com o agente novo fica
                # com NULL, e o front mostra "não informado" — sem inventar dado.
                'versao': "ADD COLUMN versao TEXT",
                'voz': "ADD COLUMN voz TEXT",
                'idioma': "ADD COLUMN idioma TEXT"
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
    
    def atualizar_metadados_operador(self, operador_id, versao=None, voz=None, idioma=None):
        """Grava versão do agente e voz/idioma vindos do registro do operador.

        SILENCIOSO de propósito: não escreve log de auditoria (ao contrário de
        update_operador), porque roda a cada (re)conexão do operador — gerar log
        aqui inundaria a tabela. Só grava os campos informados; None não apaga o
        que já existe.
        """
        campos, valores = [], []
        for chave, valor in (('versao', versao), ('voz', voz), ('idioma', idioma)):
            if valor is not None:
                campos.append(f"{chave} = ?")
                valores.append(valor)
        if not campos:
            return
        valores.append(operador_id)
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                f"UPDATE operadores SET {', '.join(campos)} WHERE id = ?",
                tuple(valores))
            self.conn.commit()
        except sqlite3.Error as e:
            logger.warning(f"Não foi possível gravar metadados do operador {operador_id}: {e}")

    def atualizar_conexao_operador(self, operador_id, ip=None, hostname=None, os_nome=None):
        """Grava o último IP/hostname/SO conhecidos do operador — colunas que já
        existiam (last_ip, last_hostname, last_os) mas nunca eram escritas.

        SILENCIOSO como atualizar_metadados_operador: roda a cada conexão, então
        não gera log de auditoria. É o que permite mostrar o último IP conhecido
        de um operador OFFLINE na tela de detalhes (antes, sem persistência, o
        IP só existia enquanto a conexão do socket estava viva)."""
        campos, valores = [], []
        for chave, valor in (('last_ip', ip), ('last_hostname', hostname), ('last_os', os_nome)):
            if valor is not None:
                campos.append(f"{chave} = ?")
                valores.append(valor)
        if not campos:
            return
        valores.append(operador_id)
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                f"UPDATE operadores SET {', '.join(campos)} WHERE id = ?",
                tuple(valores))
            self.conn.commit()
        except sqlite3.Error as e:
            logger.warning(f"Não foi possível gravar dados de conexão do operador {operador_id}: {e}")

    # Erros costumam repetir várias vezes em poucos segundos enquanto o painel
    # tenta se recuperar sozinho (retry/backoff do agente). Dentro dessa
    # janela, a mesma falha (operador+tipo+título) vira recorrência de um
    # único evento em vez de uma linha nova a cada tentativa.
    JANELA_AGRUPAMENTO_ERRO_S = 120

    # Um reinício nasce 'pendente' e só vira sucesso/falha quando o servidor
    # confirma pelo status real do operador. O processo normalmente leva uns
    # 60-90s pra subir — o timeout dá uma folga boa acima disso, pra não
    # marcar falha num reinício que só está demorando um pouco mais.
    TIMEOUT_REINICIO_PENDENTE_S = 180

    def registrar_evento(self, operador_id, tipo, ocorrido_em,
                          nivel=None, titulo=None, detalhe=None, dados_json=None):
        """Grava um evento de monitoramento (reinício ou erro) enviado pelo agente.

        Devolve o id da linha (nova ou reaproveitada por agrupamento) em caso
        de sucesso, ou None em falha — o id é usado para depois localizar e
        fechar um reinício pendente quando ele for confirmado.

        Poda oportunista: eventos com mais de 30 dias são removidos, para a
        tabela não crescer sem limite. Falha aqui nunca derruba nada — só loga.
        """
        agora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        try:
            cursor = self.conn.cursor()

            if tipo == 'erro':
                janela = (datetime.now() - timedelta(seconds=self.JANELA_AGRUPAMENTO_ERRO_S)) \
                    .strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute(
                    '''SELECT id, dados_json FROM eventos_operador
                       WHERE operador_id = ? AND tipo = ? AND titulo IS ? AND ocorrido_em >= ?
                       ORDER BY id DESC LIMIT 1''',
                    (operador_id, tipo, titulo, janela))
                existente = cursor.fetchone()
                if existente:
                    try:
                        ocorrencias = int((json.loads(existente['dados_json'] or '{}') or {}).get('ocorrencias') or 1)
                    except (TypeError, ValueError):
                        ocorrencias = 1
                    try:
                        dados = json.loads(dados_json) if dados_json else {}
                    except (TypeError, ValueError):
                        dados = {}
                    dados['ocorrencias'] = ocorrencias + 1
                    cursor.execute(
                        '''UPDATE eventos_operador
                           SET ocorrido_em = ?, nivel = ?, detalhe = ?, dados_json = ?
                           WHERE id = ?''',
                        (ocorrido_em, nivel, detalhe, json.dumps(dados, ensure_ascii=False), existente['id']))
                    self.conn.commit()
                    return existente['id']

            cursor.execute(
                '''INSERT INTO eventos_operador
                   (operador_id, tipo, nivel, titulo, detalhe, dados_json, ocorrido_em, criado_em)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (operador_id, tipo, nivel, titulo, detalhe, dados_json, ocorrido_em, agora))
            novo_id = cursor.lastrowid
            corte = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('DELETE FROM eventos_operador WHERE ocorrido_em < ?', (corte,))
            self.conn.commit()
            return novo_id
        except sqlite3.Error as e:
            logger.warning(f"Não foi possível gravar evento do operador {operador_id}: {e}")
            return None

    def mesclar_dados_reinicio(self, evento_id, dados_novos):
        """Atualiza os dados extras de um reinício ainda pendente, sem mexer
        no nível — usado quando o agente manda mais de um evento pro mesmo
        reinício (ex.: um ao iniciar, outro ao concluir do lado dele)."""
        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT dados_json FROM eventos_operador WHERE id = ?', (evento_id,))
            row = cursor.fetchone()
            if not row:
                return False
            try:
                dados = json.loads(row['dados_json']) if row['dados_json'] else {}
            except (TypeError, ValueError):
                dados = {}
            dados.update(dados_novos or {})
            cursor.execute(
                'UPDATE eventos_operador SET dados_json = ? WHERE id = ?',
                (json.dumps(dados, ensure_ascii=False), evento_id))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            logger.warning(f"Não foi possível mesclar dados do reinício {evento_id}: {e}")
            return False

    def finalizar_reinicio(self, evento_id, nivel, dados_extra=None):
        """Fecha um evento de reinício pendente: define o nível (sucesso/falha,
        já confirmado pelo status real) e mescla dados extras (fim, duracao_s)
        nos que o evento já tinha (ex.: motivo)."""
        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT dados_json FROM eventos_operador WHERE id = ?', (evento_id,))
            row = cursor.fetchone()
            if not row:
                return False
            try:
                dados = json.loads(row['dados_json']) if row['dados_json'] else {}
            except (TypeError, ValueError):
                dados = {}
            dados.update(dados_extra or {})
            cursor.execute(
                'UPDATE eventos_operador SET nivel = ?, dados_json = ? WHERE id = ?',
                (nivel, json.dumps(dados, ensure_ascii=False), evento_id))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            logger.warning(f"Não foi possível concluir o reinício (evento {evento_id}): {e}")
            return False

    def expirar_reinicios_pendentes(self, operador_id=None):
        """Fecha como falha reinícios que ficaram 'pendente' por tempo demais
        sem confirmação — chamado de forma oportunista ao listar eventos, não
        precisa de um processo em segundo plano rodando à parte."""
        try:
            corte = (datetime.now() - timedelta(seconds=self.TIMEOUT_REINICIO_PENDENTE_S)) \
                .strftime('%Y-%m-%d %H:%M:%S')
            cursor = self.conn.cursor()
            if operador_id:
                cursor.execute(
                    '''UPDATE eventos_operador SET nivel = 'falha'
                       WHERE tipo = 'reinicio' AND nivel = 'pendente'
                         AND operador_id = ? AND ocorrido_em < ?''',
                    (operador_id, corte))
            else:
                cursor.execute(
                    '''UPDATE eventos_operador SET nivel = 'falha'
                       WHERE tipo = 'reinicio' AND nivel = 'pendente' AND ocorrido_em < ?''',
                    (corte,))
            self.conn.commit()
        except sqlite3.Error as e:
            logger.warning(f"Não foi possível expirar reinícios pendentes: {e}")

    def listar_eventos(self, operador_id, tipo=None, limite=20, desde=None):
        """Retorna os eventos mais recentes do operador (opcionalmente por tipo).

        `desde` (opcional): só eventos com ocorrido_em >= esse timestamp
        ('YYYY-MM-DD HH:MM:SS'). É o que faz a lista não acumular histórico
        indefinidamente — sem isso, um evento antigo só saía quando 'limite'
        eventos mais novos o empurravam pra fora, o que podia levar dias numa
        unidade com pouco movimento."""
        self.expirar_reinicios_pendentes(operador_id)
        try:
            cursor = self.conn.cursor()
            condicoes = ['operador_id = ?']
            params = [operador_id]
            if tipo:
                condicoes.append('tipo = ?')
                params.append(tipo)
            if desde:
                condicoes.append('ocorrido_em >= ?')
                params.append(desde)
            params.append(limite)
            cursor.execute(
                f'''SELECT * FROM eventos_operador
                   WHERE {' AND '.join(condicoes)}
                   ORDER BY ocorrido_em DESC, id DESC LIMIT ?''',
                params)
            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logger.error(f"Erro ao listar eventos do operador {operador_id}: {e}")
            return []

    def contar_eventos_recentes(self, operador_id, tipo, horas=24):
        """Conta eventos de um tipo nas últimas N horas — para o resumo '24h'."""
        try:
            corte = (datetime.now() - timedelta(hours=horas)).strftime('%Y-%m-%d %H:%M:%S')
            cursor = self.conn.cursor()
            cursor.execute(
                '''SELECT COUNT(*) FROM eventos_operador
                   WHERE operador_id = ? AND tipo = ? AND ocorrido_em >= ?''',
                (operador_id, tipo, corte))
            return cursor.fetchone()[0]
        except sqlite3.Error:
            return 0

    # ── Destinatários de alertas críticos ───────────────────────────────────

    def listar_destinatarios_alerta(self):
        """Todos os destinatários cadastrados (para a tela de configuração)."""
        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT * FROM alertas_destinatarios ORDER BY nome, email')
            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logger.error(f"Erro ao listar destinatários de alerta: {e}")
            return []

    def criar_destinatario_alerta(self, nome, email, ativo=True, recebe_critico=True):
        agora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor = self.conn.cursor()
        cursor.execute(
            '''INSERT INTO alertas_destinatarios
               (nome, email, ativo, recebe_critico, data_criacao, data_atualizacao)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (nome, email, 1 if ativo else 0, 1 if recebe_critico else 0, agora, agora))
        self.conn.commit()
        return cursor.lastrowid

    def atualizar_destinatario_alerta(self, dest_id, campos: dict):
        permitidos = ('nome', 'email', 'ativo', 'recebe_critico')
        sets, valores = [], []
        for k in permitidos:
            if k in campos:
                v = campos[k]
                if k in ('ativo', 'recebe_critico'):
                    v = 1 if v else 0
                sets.append(f"{k} = ?")
                valores.append(v)
        if not sets:
            return False
        sets.append("data_atualizacao = ?")
        valores.append(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        valores.append(dest_id)
        cursor = self.conn.cursor()
        cursor.execute(f"UPDATE alertas_destinatarios SET {', '.join(sets)} WHERE id = ?", valores)
        self.conn.commit()
        return cursor.rowcount > 0

    def excluir_destinatario_alerta(self, dest_id):
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM alertas_destinatarios WHERE id = ?', (dest_id,))
        self.conn.commit()
        return cursor.rowcount > 0

    def buscar_destinatario_alerta_por_email(self, email):
        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT * FROM alertas_destinatarios WHERE email = ? COLLATE NOCASE', (email,))
            row = cursor.fetchone()
            return dict(row) if row else None
        except sqlite3.Error:
            return None

    # ── Reinícios programados ────────────────────────────────────────────────

    def listar_reinicios_programados(self):
        """Todos os agendamentos (para a tela de configuração e para o
        agendador). Ordenado por horário para a lista ficar previsível."""
        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT * FROM reinicios_programados ORDER BY horario, id')
            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logger.error(f"Erro ao listar reinícios programados: {e}")
            return []

    def criar_reinicio_programado(self, horario, dias_semana, target='ambos',
                                  descricao=None, ativo=True):
        agora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor = self.conn.cursor()
        cursor.execute(
            '''INSERT INTO reinicios_programados
               (horario, dias_semana, target, descricao, ativo, data_criacao, data_atualizacao)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (horario, dias_semana, target, descricao, 1 if ativo else 0, agora, agora))
        self.conn.commit()
        return cursor.lastrowid

    def atualizar_reinicio_programado(self, reinicio_id, campos: dict):
        permitidos = ('horario', 'dias_semana', 'target', 'descricao', 'ativo')
        sets, valores = [], []
        for k in permitidos:
            if k in campos:
                v = campos[k]
                if k == 'ativo':
                    v = 1 if v else 0
                sets.append(f"{k} = ?")
                valores.append(v)
        if not sets:
            return False
        sets.append("data_atualizacao = ?")
        valores.append(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        valores.append(reinicio_id)
        cursor = self.conn.cursor()
        cursor.execute(f"UPDATE reinicios_programados SET {', '.join(sets)} WHERE id = ?", valores)
        self.conn.commit()
        return cursor.rowcount > 0

    def excluir_reinicio_programado(self, reinicio_id):
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM reinicios_programados WHERE id = ?', (reinicio_id,))
        self.conn.commit()
        return cursor.rowcount > 0

    def obter_reinicio_programado(self, reinicio_id):
        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT * FROM reinicios_programados WHERE id = ?', (reinicio_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        except sqlite3.Error:
            return None

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