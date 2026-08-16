#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Servidor Central para gerenciamento dos operadores Tasy

Este é o ponto de entrada principal para a aplicação do servidor.
Ele garante que o eventlet seja carregado primeiro para evitar conflitos.
"""

# ETAPA 1: Monkey-patch do eventlet. DEVE ser a primeira coisa a ser executada.
# (Movido para run.py para garantir execução antecipada)
# import eventlet
# eventlet.monkey_patch()

# ETAPA 2: Imports padrão e de bibliotecas
import os
import sys
import logging
from datetime import datetime
from flask import Flask, redirect
from flask_socketio import SocketIO
from flask_cors import CORS

# ETAPA 3: Imports dos módulos da aplicação
from routes.views import views_bp
from routes.api import api_bp, init_api
from routes.websocket import register_websocket_handlers
from database import Database

# ETAPA 4: Configuração do Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - [%(threadName)s] - %(message)s')
logger = logging.getLogger("TasyServerCentral")

# Reduzir verbosidade de loggers de terceiros
logging.getLogger("werkzeug").setLevel(logging.WARNING)
logging.getLogger("socketio").setLevel(logging.WARNING)
logging.getLogger("engineio").setLevel(logging.WARNING)

# --- Fim da Lógica do Banner ---

def create_app():
    """Cria e configura a aplicação Flask e SocketIO."""
    app = Flask(__name__)
    
    # Carregar configurações do config.py
    from config import config
    app.config.from_mapping(config.get_flask_config())

    # Configurar CORS
    CORS(app, resources={r"/*": config.get_cors_config()})
    
    # Inicializar SocketIO
    # async_mode='threading': usa threads nativas do Python — sem dependências externas,
    # compatível com Python 3.14+ (eventlet não suporta 3.14+ por mudanças em _thread).
    socketio = SocketIO(
        app,
        cors_allowed_origins=config.get_cors_config()['origins'],
        async_mode='threading',
        logger=False,
        engineio_logger=False,
    )
    
    # Inicializar Banco de Dados
    db = Database(db_path=config.database.path)
    
    # Dicionário para operadores conectados
    connected_operators = {}
    
    # Registrar Blueprints
    app.register_blueprint(views_bp)
    app.register_blueprint(api_bp)
    
    # Injetar dependências nos módulos
    init_api(db, socketio, connected_operators)
    register_websocket_handlers(socketio, db, connected_operators, logger)
    
    @app.route('/operadores')
    def redirect_to_dashboard():
        return redirect('/')

    logger.info("Aplicação Flask e dependências configuradas com sucesso.")
    
    return app, socketio, db