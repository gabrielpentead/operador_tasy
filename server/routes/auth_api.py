#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rotas de autenticação e gerenciamento de usuários.

Divisão de acesso:
  /api/auth/login    público  — é a porta de entrada
  /api/auth/logout   público  — encerrar sessão nunca pode falhar por permissão
  /api/auth/me       público  — devolve 'autenticado: false' quando não há sessão
  /api/auth/senha    logado   — trocar a própria senha
  /api/auth/usuarios admin    — todo o gerenciamento de usuários
"""

import os
import time
import logging
import threading
from flask import Blueprint, request, jsonify

from core.config import config
from core.email_service import enviar_link_redefinicao, smtp_configurado

from core import auth
from core.auth import (login_required, admin_required, ROLE_ADMIN, ROLES_VALIDAS,
                  SENHA_MIN, SENHA_MAX, LOGIN_MAX, TOKEN_VALIDADE_MINUTOS)

logger = logging.getLogger("TasyServerCentral")

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

# Arquivo de primeiro acesso, removido no primeiro login bem-sucedido do admin.
_ARQUIVO_PRIMEIRO_ACESSO = None

# Controle de frequência da redefinição pública, por e-mail e por IP.
# Sem isso, o endpoint aberto viraria uma forma de encher a caixa de alguém —
# e de trocar a senha de um usuário repetidamente sem nunca ter acesso a ela.
_JANELA_SEGUNDOS = 300      # 5 minutos
_MAX_POR_JANELA = 3
# Links recusados toleram mais tentativas: o token tem 43 caracteres sorteados,
# adivinhá-lo é inviável, e um teto baixo demais atrapalharia quem clicou duas
# vezes num link vencido sem entender o motivo.
_MAX_LINKS_RECUSADOS = 10
_tentativas = {}
_trava_tentativas = threading.Lock()


def _montar_link(token: str) -> str:
    """Monta o link a partir do endereço que o navegador usou na requisição.

    Usar request.url_root evita ter de configurar a URL pública num arquivo: em
    rede interna, o host que a pessoa acessou é exatamente o que funciona para
    ela. Se o servidor for publicado com outro nome, basta acessar por esse
    nome que o link sai correto.
    """
    return f"{request.url_root.rstrip('/')}/?redefinir={token}"


def _excedeu_limite(chave: str, maximo: int = _MAX_POR_JANELA) -> bool:
    """Registra a tentativa e diz se o limite foi estourado."""
    agora = time.time()
    with _trava_tentativas:
        registros = [t for t in _tentativas.get(chave, []) if agora - t < _JANELA_SEGUNDOS]
        if len(registros) >= maximo:
            _tentativas[chave] = registros
            return True
        registros.append(agora)
        _tentativas[chave] = registros
        # Limpeza oportunista para o dicionário não crescer indefinidamente
        if len(_tentativas) > 500:
            for k in [k for k, v in _tentativas.items()
                      if not any(agora - t < _JANELA_SEGUNDOS for t in v)]:
                _tentativas.pop(k, None)
        return False


def _bloqueado(chave: str, maximo: int) -> bool:
    """Só consulta o limite, sem registrar nada.

    Usado onde a tentativa só deve contar se ela realmente falhar — assim quem
    erra a digitação da própria senha não gasta o mesmo orçamento de quem está
    tentando adivinhar um link.
    """
    agora = time.time()
    with _trava_tentativas:
        registros = [t for t in _tentativas.get(chave, []) if agora - t < _JANELA_SEGUNDOS]
        _tentativas[chave] = registros
        return len(registros) >= maximo


def init_auth_routes(caminho_primeiro_acesso=None):
    global _ARQUIVO_PRIMEIRO_ACESSO
    _ARQUIVO_PRIMEIRO_ACESSO = caminho_primeiro_acesso


# ── Sessão ──────────────────────────────────────────────────────────────────

@auth_bp.route('/login', methods=['POST'])
def login():
    try:
        dados = request.get_json(silent=True) or {}
        usuario, erro = auth.autenticar(dados.get('login', ''), dados.get('senha', ''))

        if erro:
            # Log sem a senha, e sem confirmar se o login existe.
            logger.warning(f"Login recusado para '{dados.get('login', '')}' "
                           f"de {request.remote_addr}")
            return jsonify({'success': False, 'error': erro}), 401

        auth.abrir_sessao(usuario)
        logger.info(f"Login: '{usuario['login']}' ({usuario['role']}) de {request.remote_addr}")

        # O arquivo de primeiro acesso perde a razão de existir assim que
        # alguém entra — some sozinho para não ficar senha em disco.
        if _ARQUIVO_PRIMEIRO_ACESSO and os.path.exists(_ARQUIVO_PRIMEIRO_ACESSO):
            try:
                os.remove(_ARQUIVO_PRIMEIRO_ACESSO)
                logger.info("Arquivo de primeiro acesso removido após login.")
            except Exception:
                pass

        return jsonify({'success': True, 'usuario': usuario})
    except Exception as e:
        logger.error(f"Erro no login: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Erro interno'}), 500


@auth_bp.route('/logout', methods=['POST'])
def logout():
    u = auth.usuario_atual()
    auth.encerrar_sessao()
    if u:
        logger.info(f"Logout: '{u['login']}'")
    return jsonify({'success': True})


@auth_bp.route('/me', methods=['GET'])
def me():
    """Quem está logado. Usado pelo frontend ao carregar, para decidir entre
    mostrar o login ou o painel."""
    u = auth.usuario_atual()
    if u is None:
        return jsonify({'success': True, 'autenticado': False})
    return jsonify({'success': True, 'autenticado': True, 'usuario': u})


@auth_bp.route('/senha', methods=['POST'])
@login_required
def trocar_propria_senha():
    """Troca da própria senha. Exige a senha atual — assim, uma sessão deixada
    aberta não permite que outra pessoa assuma a conta."""
    try:
        dados = request.get_json(silent=True) or {}
        atual = dados.get('senha_atual', '')
        nova = dados.get('senha_nova', '')

        if len(nova) < SENHA_MIN:
            return jsonify({'success': False,
                            'error': f'A nova senha precisa ter ao menos {SENHA_MIN} caracteres'}), 400
        if len(nova) > SENHA_MAX:
            return jsonify({'success': False,
                            'error': f'A nova senha deve ter no máximo {SENHA_MAX} caracteres'}), 400

        u = auth.usuario_atual()
        linha = auth.buscar_por_id(u['id'])
        if not auth.conferir_senha(linha['senha_hash'], atual):
            return jsonify({'success': False, 'error': 'Senha atual incorreta'}), 400

        auth.atualizar_usuario(u['id'], {'senha': nova})
        logger.info(f"Senha alterada pelo próprio usuário '{u['login']}'")
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Erro ao trocar senha: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Erro interno'}), 500


@auth_bp.route('/esqueci-senha', methods=['POST'])
def esqueci_senha():
    """Envia um link para a pessoa escolher a nova senha. Rota PÚBLICA.

    A senha NÃO é alterada aqui. Só muda quando o link é aberto e a nova senha
    é digitada — assim um pedido feito por engano (ou por terceiro) não tranca
    ninguém para fora do sistema.

    A resposta é sempre a mesma, exista ou não o e-mail informado. Isso impede
    que a rota seja usada para descobrir quais endereços têm conta — quem não
    tem cadastro simplesmente não recebe nada.

    A única exceção é o SMTP não configurado: aí a mensagem é explícita, porque
    o problema é do servidor e alguém precisa agir.
    """
    RESPOSTA_PADRAO = {
        'success': True,
        'mensagem': 'Se este e-mail estiver cadastrado, enviamos um link para '
                    'redefinir a senha. Verifique sua caixa de entrada.'
    }
    try:
        dados = request.get_json(silent=True) or {}
        email = (dados.get('email') or '').strip().lower()

        if not smtp_configurado(config.email):
            logger.error("Redefinição solicitada, mas o SMTP não está configurado.")
            return jsonify({'success': False,
                            'error': 'O envio de e-mail não está configurado no servidor. '
                                     'Procure o NTI.'}), 503

        if not email or not auth.email_valido(email):
            return jsonify({'success': False, 'error': 'Informe um e-mail válido'}), 400

        ip = request.remote_addr or 'desconhecido'
        if _excedeu_limite(f'email:{email}') or _excedeu_limite(f'ip:{ip}'):
            logger.warning(f"Limite de redefinições excedido (e-mail={email}, ip={ip})")
            return jsonify({'success': False,
                            'error': 'Muitas tentativas. Aguarde alguns minutos.'}), 429

        linha = auth.buscar_por_email(email)

        # Conta inexistente ou desativada: resposta idêntica, nada é enviado.
        if linha is None or not linha['ativo']:
            logger.info(f"Redefinição pedida para e-mail sem conta ativa: {email}")
            return jsonify(RESPOSTA_PADRAO)

        token = auth.criar_token_redefinicao(linha['id'], ip)
        enviado, erro = enviar_link_redefinicao(
            config.email, email, linha['nome'], linha['login'],
            _montar_link(token), TOKEN_VALIDADE_MINUTOS)

        if not enviado:
            logger.error(f"Link de redefinição de '{linha['login']}' não pôde ser enviado: {erro}")
            return jsonify({'success': False,
                            'error': 'Não foi possível enviar o e-mail agora. '
                                     'Tente mais tarde ou procure o NTI.'}), 502

        logger.info(f"Link de redefinição enviado para '{linha['login']}'")
        return jsonify(RESPOSTA_PADRAO)

    except Exception as e:
        logger.error(f"Erro na redefinição por e-mail: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Erro interno'}), 500


@auth_bp.route('/validar-token', methods=['POST'])
def validar_token():
    """Diz se o link ainda vale, para a tela decidir o que mostrar. PÚBLICA.

    Não consome o token e não devolve nada sensível — só o nome e o login, para
    a pessoa confirmar que está redefinindo a conta certa.

    O token vai no corpo, não na URL, para não ficar registrado no log de
    acesso do servidor nem no histórico de proxies.
    """
    try:
        dados = request.get_json(silent=True) or {}
        usuario, erro = auth.validar_token((dados.get('token') or '').strip())
        if erro:
            return jsonify({'success': False, 'valido': False, 'error': erro}), 400
        return jsonify({'success': True, 'valido': True,
                        'nome': usuario['nome'], 'login': usuario['login']})
    except Exception as e:
        logger.error(f"Erro ao validar token: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Erro interno'}), 500


@auth_bp.route('/redefinir', methods=['POST'])
def redefinir_com_token():
    """Consome o link e grava a senha escolhida pela própria pessoa. PÚBLICA."""
    try:
        dados = request.get_json(silent=True) or {}
        token = (dados.get('token') or '').strip()
        senha = dados.get('senha') or ''

        # Só links recusados contam para o limite. Quem já está com o link
        # certo na mão e apenas errou o tamanho da senha não é atacante — se
        # cada tentativa contasse, a pessoa se trancaria sozinha para fora.
        ip = request.remote_addr or 'desconhecido'
        if _bloqueado(f'redef:{ip}', _MAX_LINKS_RECUSADOS):
            logger.warning(f"Limite de links recusados excedido (ip={ip})")
            return jsonify({'success': False,
                            'error': 'Muitas tentativas. Aguarde alguns minutos.'}), 429

        if len(senha) < SENHA_MIN:
            return jsonify({'success': False,
                            'error': f'A senha precisa ter ao menos {SENHA_MIN} caracteres'}), 400
        if len(senha) > SENHA_MAX:
            return jsonify({'success': False,
                            'error': f'A senha deve ter no máximo {SENHA_MAX} caracteres'}), 400

        usuario, erro = auth.consumir_token(token, senha)
        if erro:
            _excedeu_limite(f'redef:{ip}', _MAX_LINKS_RECUSADOS)
            logger.warning(f"Redefinição recusada para link vindo de {ip}: {erro}")
            return jsonify({'success': False, 'error': erro}), 400

        logger.info(f"Senha redefinida pelo link por '{usuario['login']}'")
        return jsonify({'success': True,
                        'login': usuario['login'],
                        'mensagem': 'Senha alterada. Você já pode entrar com ela.'})
    except Exception as e:
        logger.error(f"Erro ao redefinir com token: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Erro interno'}), 500


# ── Gerenciamento de usuários (somente administradores) ──────────────────────

@auth_bp.route('/usuarios', methods=['GET'])
@admin_required
def listar():
    return jsonify({'success': True, 'usuarios': auth.listar_usuarios()})


@auth_bp.route('/usuarios', methods=['POST'])
@admin_required
def criar():
    try:
        d = request.get_json(silent=True) or {}
        nome = (d.get('nome') or '').strip()
        login_novo = (d.get('login') or '').strip().lower()
        email = (d.get('email') or '').strip().lower()
        senha = d.get('senha') or ''
        role = d.get('role') or 'operador'

        if not nome or not login_novo:
            return jsonify({'success': False, 'error': 'Nome e login são obrigatórios'}), 400
        if len(login_novo) > LOGIN_MAX:
            return jsonify({'success': False,
                            'error': f'O usuário deve ter no máximo {LOGIN_MAX} caracteres'}), 400
        # E-mail obrigatório no cadastro: é por ele que a futura redefinição de
        # senha vai identificar o usuário.
        if not email:
            return jsonify({'success': False, 'error': 'E-mail é obrigatório'}), 400
        if not auth.email_valido(email):
            return jsonify({'success': False, 'error': 'E-mail inválido'}), 400
        if auth.buscar_por_email(email) is not None:
            return jsonify({'success': False, 'error': 'Já existe um usuário com esse e-mail'}), 409
        if len(senha) < SENHA_MIN:
            return jsonify({'success': False,
                            'error': f'A senha precisa ter ao menos {SENHA_MIN} caracteres'}), 400
        if len(senha) > SENHA_MAX:
            return jsonify({'success': False,
                            'error': f'A senha deve ter no máximo {SENHA_MAX} caracteres'}), 400
        if role not in ROLES_VALIDAS:
            return jsonify({'success': False, 'error': 'Permissão inválida'}), 400
        if auth.buscar_por_login(login_novo) is not None:
            return jsonify({'success': False, 'error': 'Já existe um usuário com esse login'}), 409

        usuario = auth.criar_usuario(nome, login_novo, senha, role,
                                     bool(d.get('ativo', True)), email=email)
        logger.info(f"Usuário '{login_novo}' ({role}) criado por "
                    f"'{auth.usuario_atual()['login']}'")
        return jsonify({'success': True, 'usuario': usuario}), 201
    except Exception as e:
        logger.error(f"Erro ao criar usuário: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Erro interno'}), 500


@auth_bp.route('/usuarios/<int:usuario_id>', methods=['PUT'])
@admin_required
def editar(usuario_id):
    try:
        d = request.get_json(silent=True) or {}
        atual = auth.usuario_atual()
        alvo = auth.buscar_por_id(usuario_id)
        if alvo is None:
            return jsonify({'success': False, 'error': 'Usuário não encontrado'}), 404

        campos = {}
        if 'nome' in d and str(d['nome']).strip():
            campos['nome'] = str(d['nome']).strip()

        if 'login' in d and str(d['login']).strip():
            novo_login = str(d['login']).strip().lower()
            if len(novo_login) > LOGIN_MAX:
                return jsonify({'success': False,
                                'error': f'O usuário deve ter no máximo {LOGIN_MAX} caracteres'}), 400
            existente = auth.buscar_por_login(novo_login)
            if existente is not None and existente['id'] != usuario_id:
                return jsonify({'success': False, 'error': 'Já existe um usuário com esse login'}), 409
            campos['login'] = novo_login

        if 'email' in d:
            novo_email = str(d['email'] or '').strip().lower()
            if novo_email:
                if not auth.email_valido(novo_email):
                    return jsonify({'success': False, 'error': 'E-mail inválido'}), 400
                existente = auth.buscar_por_email(novo_email)
                if existente is not None and existente['id'] != usuario_id:
                    return jsonify({'success': False,
                                    'error': 'Já existe um usuário com esse e-mail'}), 409
            campos['email'] = novo_email

        if 'role' in d:
            if d['role'] not in ROLES_VALIDAS:
                return jsonify({'success': False, 'error': 'Permissão inválida'}), 400
            campos['role'] = d['role']

        if 'ativo' in d:
            campos['ativo'] = bool(d['ativo'])

        if d.get('senha'):
            if len(d['senha']) < SENHA_MIN:
                return jsonify({'success': False,
                                'error': f'A senha precisa ter ao menos {SENHA_MIN} caracteres'}), 400
            if len(d['senha']) > SENHA_MAX:
                return jsonify({'success': False,
                                'error': f'A senha deve ter no máximo {SENHA_MAX} caracteres'}), 400
            campos['senha'] = d['senha']

        # Trava de segurança: o painel não pode ficar sem administrador ativo.
        virou_nao_admin = campos.get('role', alvo['role']) != ROLE_ADMIN
        virou_inativo = not campos.get('ativo', bool(alvo['ativo']))
        if alvo['role'] == ROLE_ADMIN and (virou_nao_admin or virou_inativo):
            if auth.contar_admins_ativos(excluindo_id=usuario_id) == 0:
                return jsonify({'success': False,
                                'error': 'Este é o último administrador ativo. '
                                         'Promova outro usuário antes de alterá-lo.'}), 400

        # Ninguém se auto-desativa nem se auto-rebaixa: evita perder o acesso
        # por engano no meio de uma edição.
        if usuario_id == atual['id']:
            if campos.get('ativo') is False:
                return jsonify({'success': False,
                                'error': 'Você não pode desativar a própria conta'}), 400
            if campos.get('role') and campos['role'] != ROLE_ADMIN:
                return jsonify({'success': False,
                                'error': 'Você não pode remover a própria permissão de administrador'}), 400

        usuario = auth.atualizar_usuario(usuario_id, campos)
        logger.info(f"Usuário id={usuario_id} alterado por '{atual['login']}' "
                    f"(campos: {', '.join(k for k in campos if k != 'senha')}"
                    f"{'; senha redefinida' if 'senha' in campos else ''})")
        return jsonify({'success': True, 'usuario': usuario})
    except Exception as e:
        logger.error(f"Erro ao editar usuário: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Erro interno'}), 500


@auth_bp.route('/usuarios/<int:usuario_id>/redefinir-senha', methods=['POST'])
@admin_required
def redefinir_senha_usuario(usuario_id):
    """Administrador dispara o link de redefinição para o e-mail do usuário.

    Nem o administrador chega a conhecer a nova senha: quem a escolhe é o
    próprio dono da conta, ao abrir o link.
    """
    try:
        alvo = auth.buscar_por_id(usuario_id)
        if alvo is None:
            return jsonify({'success': False, 'error': 'Usuário não encontrado'}), 404
        if not alvo['email']:
            return jsonify({'success': False,
                            'error': 'Este usuário não tem e-mail cadastrado. '
                                     'Edite o usuário e informe um e-mail primeiro.'}), 400
        if not smtp_configurado(config.email):
            return jsonify({'success': False,
                            'error': 'O envio de e-mail não está configurado no servidor.'}), 503

        token = auth.criar_token_redefinicao(usuario_id, request.remote_addr)
        enviado, erro = enviar_link_redefinicao(
            config.email, alvo['email'], alvo['nome'], alvo['login'],
            _montar_link(token), TOKEN_VALIDADE_MINUTOS)

        if not enviado:
            logger.error(f"Link de redefinição de '{alvo['login']}' falhou: {erro}")
            return jsonify({'success': False,
                            'error': f'Não foi possível enviar o e-mail: {erro}'}), 502

        logger.info(f"Link de redefinição de '{alvo['login']}' enviado por "
                    f"'{auth.usuario_atual()['login']}'")
        return jsonify({'success': True,
                        'mensagem': f"Link de redefinição enviado para {alvo['email']}"})
    except Exception as e:
        logger.error(f"Erro ao redefinir senha: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Erro interno'}), 500


@auth_bp.route('/usuarios/<int:usuario_id>', methods=['DELETE'])
@admin_required
def excluir(usuario_id):
    try:
        atual = auth.usuario_atual()
        alvo = auth.buscar_por_id(usuario_id)
        if alvo is None:
            return jsonify({'success': False, 'error': 'Usuário não encontrado'}), 404

        if usuario_id == atual['id']:
            return jsonify({'success': False,
                            'error': 'Você não pode excluir a própria conta'}), 400

        if alvo['role'] == ROLE_ADMIN and auth.contar_admins_ativos(excluindo_id=usuario_id) == 0:
            return jsonify({'success': False,
                            'error': 'Este é o último administrador ativo e não pode ser excluído.'}), 400

        auth.excluir_usuario(usuario_id)
        logger.info(f"Usuário '{alvo['login']}' excluído por '{atual['login']}'")
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Erro ao excluir usuário: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Erro interno'}), 500
