#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# server/routes/views.py - Rotas para renderização das views

import os
from flask import Blueprint, redirect, send_from_directory
import logging

logger = logging.getLogger("TasyServerCentral")

views_bp = Blueprint('views', __name__)

BUILD_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static', 'app'
)


def _servir_app():
    """Entrega o index.html do build React.

    Este é o ÚNICO ponto de entrada da interface. A versão antiga em Jinja
    (templates/index.html) deixou de ser servida: ela não conhecia a
    autenticação, então a raiz abria um painel sem login enquanto a aplicação
    real ficava protegida em /app — um caminho paralelo que não deveria existir.

    Servir o mesmo arquivo em '/' e '/app' garante que qualquer endereço leve ao
    mesmo fluxo, que começa pela verificação de sessão em /api/auth/me.
    """
    index_path = os.path.join(BUILD_DIR, 'index.html')
    if not os.path.exists(index_path):
        logger.warning("Build do React não encontrado em static/app. Rode 'npm run build'.")
        return (
            "<h3>Build do React não encontrado.</h3>"
            "<p>Rode <code>npm install &amp;&amp; npm run build</code> dentro de "
            "<code>server/frontend</code>.</p>",
            503,
        )

    resposta = send_from_directory(BUILD_DIR, 'index.html')
    # no-store: o index referencia os bundles por hash, então uma cópia velha em
    # cache faria o navegador seguir carregando o JS antigo depois de um deploy.
    # Os assets em si continuam cacheáveis pelo próprio hash no nome.
    resposta.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resposta.headers['Pragma'] = 'no-cache'
    resposta.headers['Expires'] = '0'
    return resposta


@views_bp.route('/')
def index():
    """Raiz: a aplicação atual, que exige login."""
    logger.info("Acesso à aplicação")
    return _servir_app()


@views_bp.route('/app')
@views_bp.route('/app/')
def app_react():
    """Mantido por compatibilidade — serve exatamente o mesmo arquivo da raiz."""
    return _servir_app()


@views_bp.route('/operadores')
def operadores_redirect():
    """Endereço antigo: leva à aplicação."""
    return redirect('/')
