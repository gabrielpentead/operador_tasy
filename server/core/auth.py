#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Autenticação e controle de acesso do painel administrativo.

MECANISMO ESCOLHIDO — sessão do Flask em cookie assinado.
Motivos, todos ligados ao que o projeto já tem:

  - A `secret_key` já existe e é persistida em server_config.json, gerada com
    secrets.token_hex(32). Nada novo precisa ser criado ou guardado.
  - O cookie é HttpOnly: o JavaScript da página não consegue lê-lo, então não
    há token trafegando por localStorage nem exposto a XSS.
  - O mesmo cookie acompanha as chamadas REST e o Socket.IO, sem gambiarra.
  - Não exige dependência nova. O Werkzeug (que já vem com o Flask 2.2.5)
    fornece o hash PBKDF2-SHA256.

IMPORTANTE — os operadores dos painéis NÃO passam por aqui. Eles se registram
pelo evento `registrar_operador` do Socket.IO, que permanece intocado. Proteger
as rotas REST não afeta os painéis em produção.
"""

import re
import hashlib
import logging
import sqlite3
import secrets
from datetime import datetime, timedelta
from functools import wraps

from flask import session, jsonify, request
from werkzeug.security import generate_password_hash, check_password_hash

logger = logging.getLogger("TasyServerCentral")

ROLE_ADMIN = 'admin'
ROLE_OPERADOR = 'operador'
ROLES_VALIDAS = (ROLE_ADMIN, ROLE_OPERADOR)

# Limites de tamanho de login e senha.
#
# O máximo vale para CADASTRO e EDIÇÃO. A rota de login NÃO o aplica de
# propósito: uma conta criada antes deste limite continuaria válida no banco, e
# recusá-la na entrada trancaria a pessoa para fora sem qualquer ganho de
# segurança.
SENHA_MIN = 6
SENHA_MAX = 15
LOGIN_MAX = 15

# Validade do link de redefinicao. Curta de proposito: o link da acesso a
# trocar a senha de alguem, entao quanto menor a janela, melhor.
TOKEN_VALIDADE_MINUTOS = 60

# Validação de e-mail deliberadamente simples: confere o formato básico sem
# tentar reimplementar a RFC. Quem confirma que o endereço existe de verdade é
# o envio da redefinição de senha, quando ele for implementado.
_RE_EMAIL = re.compile(r'^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$')


def email_valido(email: str) -> bool:
    return bool(_RE_EMAIL.match((email or '').strip()))

_db = None


def init_auth(database):
    """Recebe a instância de Database usada pelo restante da aplicação."""
    global _db
    _db = database


# ── Hash ────────────────────────────────────────────────────────────────────

def gerar_hash(senha: str) -> str:
    """PBKDF2-SHA256 com salt aleatório, via Werkzeug. Nunca guardamos a senha."""
    return generate_password_hash(senha, method='pbkdf2:sha256', salt_length=16)


def conferir_senha(hash_armazenado: str, senha: str) -> bool:
    try:
        return check_password_hash(hash_armazenado, senha)
    except Exception:
        return False


# ── Acesso ao banco ─────────────────────────────────────────────────────────

def _linha_para_dict(row) -> dict:
    """Converte a linha do banco em dicionário SEM o hash da senha.

    O hash nunca sai desta camada: nenhuma resposta de API deve conter senha,
    nem mesmo em forma de hash.
    """
    if row is None:
        return None
    d = dict(row)
    d.pop('senha_hash', None)
    d['ativo'] = bool(d.get('ativo', 1))
    return d


def buscar_por_login(login: str):
    cur = _db.conn.cursor()
    cur.execute('SELECT * FROM usuarios WHERE login = ? COLLATE NOCASE', (login,))
    return cur.fetchone()


def buscar_por_email(email: str):
    """Busca por e-mail. Será a porta de entrada da redefinição de senha."""
    if not (email or '').strip():
        return None
    cur = _db.conn.cursor()
    cur.execute('SELECT * FROM usuarios WHERE email = ? COLLATE NOCASE', (email.strip(),))
    return cur.fetchone()


def buscar_por_id(usuario_id: int):
    cur = _db.conn.cursor()
    cur.execute('SELECT * FROM usuarios WHERE id = ?', (usuario_id,))
    return cur.fetchone()


def listar_usuarios() -> list:
    cur = _db.conn.cursor()
    cur.execute('SELECT * FROM usuarios ORDER BY nome COLLATE NOCASE')
    return [_linha_para_dict(r) for r in cur.fetchall()]


def contar_usuarios() -> int:
    cur = _db.conn.cursor()
    cur.execute('SELECT COUNT(*) FROM usuarios')
    return cur.fetchone()[0]


def contar_admins_ativos(excluindo_id: int = None) -> int:
    """Quantos administradores ativos existem, opcionalmente ignorando um id.

    Usado para impedir que o último administrador seja desativado, rebaixado ou
    excluído — cenário que deixaria o painel sem ninguém capaz de administrá-lo.
    """
    cur = _db.conn.cursor()
    if excluindo_id is None:
        cur.execute("SELECT COUNT(*) FROM usuarios WHERE role = ? AND ativo = 1", (ROLE_ADMIN,))
    else:
        cur.execute("SELECT COUNT(*) FROM usuarios WHERE role = ? AND ativo = 1 AND id != ?",
                    (ROLE_ADMIN, excluindo_id))
    return cur.fetchone()[0]


def criar_usuario(nome: str, login: str, senha: str, role: str = ROLE_OPERADOR,
                  ativo: bool = True, email: str = None) -> dict:
    agora = datetime.now().isoformat(timespec='seconds')
    cur = _db.conn.cursor()
    cur.execute(
        '''INSERT INTO usuarios (nome, login, email, senha_hash, role, ativo,
                                 data_criacao, data_atualizacao)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
        (nome.strip(), login.strip().lower(), (email or '').strip().lower() or None,
         gerar_hash(senha), role, 1 if ativo else 0, agora, agora)
    )
    _db.conn.commit()
    return _linha_para_dict(buscar_por_id(cur.lastrowid))


def atualizar_usuario(usuario_id: int, campos: dict) -> dict:
    """Atualiza apenas os campos informados. A senha, se vier, é convertida em hash."""
    permitidos = {'nome', 'login', 'role', 'ativo', 'email'}
    sets, valores = [], []

    for chave, valor in campos.items():
        if chave in permitidos:
            sets.append(f"{chave} = ?")
            if chave == 'ativo':
                valores.append(1 if valor else 0)
            elif chave in ('login', 'email'):
                valores.append(str(valor).strip().lower() or None)
            else:
                valores.append(valor)

    if campos.get('senha'):
        sets.append("senha_hash = ?")
        valores.append(gerar_hash(campos['senha']))

    if not sets:
        return _linha_para_dict(buscar_por_id(usuario_id))

    sets.append("data_atualizacao = ?")
    valores.append(datetime.now().isoformat(timespec='seconds'))
    valores.append(usuario_id)

    cur = _db.conn.cursor()
    # Os nomes de coluna vêm da lista fixa `permitidos`, nunca do cliente.
    cur.execute(f"UPDATE usuarios SET {', '.join(sets)} WHERE id = ?", valores)
    _db.conn.commit()
    return _linha_para_dict(buscar_por_id(usuario_id))


def excluir_usuario(usuario_id: int) -> bool:
    cur = _db.conn.cursor()
    cur.execute('DELETE FROM usuarios WHERE id = ?', (usuario_id,))
    _db.conn.commit()
    return cur.rowcount > 0


def registrar_acesso(usuario_id: int):
    try:
        cur = _db.conn.cursor()
        cur.execute('UPDATE usuarios SET ultimo_acesso = ? WHERE id = ?',
                    (datetime.now().isoformat(timespec='seconds'), usuario_id))
        _db.conn.commit()
    except Exception as e:
        logger.warning(f"Não foi possível registrar último acesso: {e}")


# ── Sessão ──────────────────────────────────────────────────────────────────

def autenticar(login: str, senha: str):
    """Valida credenciais. Devolve (usuario, erro).

    A mensagem de erro é a mesma para login inexistente e senha errada, para não
    revelar quais logins existem.
    """
    linha = buscar_por_login(login or '')
    if linha is None or not conferir_senha(linha['senha_hash'], senha or ''):
        return None, 'Usuário ou senha inválidos'
    if not linha['ativo']:
        return None, 'Usuário desativado. Procure um administrador.'
    return _linha_para_dict(linha), None


def abrir_sessao(usuario: dict):
    """Grava o vínculo na sessão. Só o id e um marcador — nada sensível."""
    session.clear()
    session['usuario_id'] = usuario['id']
    session['token'] = secrets.token_urlsafe(16)
    session.permanent = True
    registrar_acesso(usuario['id'])


def encerrar_sessao():
    session.clear()


def usuario_atual():
    """Usuário da sessão, revalidado no banco a cada chamada.

    A revalidação é o que faz a desativação surtir efeito na hora: quem for
    desativado ou excluído perde o acesso na requisição seguinte, sem precisar
    esperar o cookie expirar.
    """
    uid = session.get('usuario_id')
    if not uid:
        return None
    linha = buscar_por_id(uid)
    if linha is None or not linha['ativo']:
        session.clear()
        return None
    return _linha_para_dict(linha)


# ── Decoradores ─────────────────────────────────────────────────────────────

def login_required(f):
    """Exige sessão válida. Responde 401 em JSON, que o frontend usa para
    redirecionar ao login."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if usuario_atual() is None:
            return jsonify({'success': False, 'error': 'Não autenticado',
                            'codigo': 'nao_autenticado'}), 401
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    """Exige sessão válida COM papel de administrador.

    Esta verificação é do servidor. Esconder o botão no frontend é conveniência
    visual; quem garante o controle é este decorador.
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        u = usuario_atual()
        if u is None:
            return jsonify({'success': False, 'error': 'Não autenticado',
                            'codigo': 'nao_autenticado'}), 401
        if u.get('role') != ROLE_ADMIN:
            logger.warning(
                f"Acesso administrativo negado a '{u.get('login')}' em {request.path}")
            return jsonify({'success': False, 'error': 'Permissão insuficiente',
                            'codigo': 'sem_permissao'}), 403
        return f(*args, **kwargs)
    return wrapper


# ── Primeiro administrador ──────────────────────────────────────────────────

def garantir_admin_inicial(caminho_aviso: str = None):
    """Cria o primeiro administrador quando o banco ainda não tem usuários.

    A senha é sorteada na hora, nunca fica escrita no código. Ela é mostrada uma
    única vez no console e gravada num arquivo de primeiro acesso, que é apagado
    sozinho assim que esse administrador entrar pela primeira vez.

    Devolve a senha gerada, ou None se já existia algum usuário.
    """
    try:
        if contar_usuarios() > 0:
            return None

        senha = secrets.token_urlsafe(10)   # 14 caracteres, dentro de SENHA_MAX
        criar_usuario(nome='Administrador', login='admin', senha=senha,
                      role=ROLE_ADMIN, ativo=True)

        aviso = (
            "\n" + "=" * 64 + "\n"
            "  PRIMEIRO ACESSO — ADMINISTRADOR CRIADO\n" +
            "=" * 64 + "\n"
            f"  Usuário: admin\n"
            f"  Senha:   {senha}\n\n"
            "  Anote esta senha: ela não será exibida novamente.\n"
            "  Troque-a após o primeiro acesso em Configurações > Usuários.\n" +
            "=" * 64 + "\n"
        )
        print(aviso)
        logger.warning("Primeiro administrador criado. Senha exibida no console.")

        if caminho_aviso:
            try:
                with open(caminho_aviso, 'w', encoding='utf-8') as f:
                    f.write(aviso)
                logger.warning(f"Credenciais de primeiro acesso em {caminho_aviso} "
                               f"(removido automaticamente após o primeiro login).")
            except Exception:
                pass

        return senha
    except sqlite3.Error as e:
        logger.error(f"Falha ao criar administrador inicial: {e}")
        return None


# ── Tokens de redefinicao de senha ──────────────────────────────────────────

def _hash_token(token: str) -> str:
    """SHA-256 do token. E o que vai para o banco — o token em si so existe
    dentro do link enviado por e-mail."""
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def criar_token_redefinicao(usuario_id: int, ip: str = None) -> str:
    """Gera um token de uso unico e devolve o valor em claro.

    Pedidos anteriores do mesmo usuario sao invalidados: se a pessoa pediu duas
    vezes, apenas o link mais recente deve funcionar.
    """
    agora = datetime.now()
    token = secrets.token_urlsafe(32)

    cur = _db.conn.cursor()
    cur.execute("""UPDATE redefinicoes_senha SET usado_em = ?
                   WHERE usuario_id = ? AND usado_em IS NULL""",
                (agora.isoformat(timespec='seconds'), usuario_id))
    cur.execute("""INSERT INTO redefinicoes_senha
                   (usuario_id, token_hash, criado_em, expira_em, ip_solicitante)
                   VALUES (?, ?, ?, ?, ?)""",
                (usuario_id, _hash_token(token),
                 agora.isoformat(timespec='seconds'),
                 (agora + timedelta(minutes=TOKEN_VALIDADE_MINUTOS)).isoformat(timespec='seconds'),
                 ip))
    _db.conn.commit()
    return token


def validar_token(token: str):
    """Devolve (usuario, erro). Nao consome o token — serve para a tela decidir
    se mostra o formulario ou a mensagem de link invalido."""
    if not token:
        return None, 'Link inválido'

    cur = _db.conn.cursor()
    cur.execute('SELECT * FROM redefinicoes_senha WHERE token_hash = ?', (_hash_token(token),))
    pedido = cur.fetchone()

    if pedido is None:
        return None, 'Link inválido ou já utilizado'
    if pedido['usado_em']:
        return None, 'Este link já foi utilizado'
    try:
        if datetime.fromisoformat(pedido['expira_em']) < datetime.now():
            return None, 'Este link expirou. Solicite uma nova redefinição.'
    except ValueError:
        return None, 'Link inválido'

    linha = buscar_por_id(pedido['usuario_id'])
    if linha is None or not linha['ativo']:
        return None, 'Conta indisponível. Procure um administrador.'

    return _linha_para_dict(linha), None


def consumir_token(token: str, senha_nova: str):
    """Valida o token, troca a senha e marca o pedido como usado.

    Devolve (usuario, erro). A marcacao acontece na mesma operacao da troca,
    para o link nao poder ser reaproveitado.
    """
    usuario, erro = validar_token(token)
    if erro:
        return None, erro

    atualizar_usuario(usuario['id'], {'senha': senha_nova})

    cur = _db.conn.cursor()
    cur.execute("""UPDATE redefinicoes_senha SET usado_em = ?
                   WHERE token_hash = ?""",
                (datetime.now().isoformat(timespec='seconds'), _hash_token(token)))
    _db.conn.commit()
    return usuario, None


def limpar_tokens_expirados():
    """Remove pedidos vencidos ha mais de 7 dias, para a tabela nao crescer."""
    try:
        limite = (datetime.now() - timedelta(days=7)).isoformat(timespec='seconds')
        cur = _db.conn.cursor()
        cur.execute('DELETE FROM redefinicoes_senha WHERE expira_em < ?', (limite,))
        _db.conn.commit()
        return cur.rowcount
    except Exception:
        return 0


def redefinir_senha_admin() -> str:
    """Sorteia uma nova senha para o login 'admin'. Usado para recuperação.

    Reativa a conta se estiver desativada — caso contrário, uma desativação
    acidental do único administrador deixaria o painel inacessível.
    """
    senha = secrets.token_urlsafe(10)   # 14 caracteres, dentro de SENHA_MAX
    linha = buscar_por_login('admin')
    if linha is None:
        criar_usuario(nome='Administrador', login='admin', senha=senha,
                      role=ROLE_ADMIN, ativo=True)
    else:
        atualizar_usuario(linha['id'], {'senha': senha, 'ativo': True, 'role': ROLE_ADMIN})
    return senha
