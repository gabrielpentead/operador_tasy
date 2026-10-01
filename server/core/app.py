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
from datetime import datetime, timedelta
from flask import Flask
from flask_socketio import SocketIO
from flask_cors import CORS

# ETAPA 3: Imports dos módulos da aplicação
from routes.views import views_bp
from routes.api import api_bp, init_api
from routes.websocket import register_websocket_handlers
from routes.auth_api import auth_bp, init_auth_routes
from routes.alertas_api import alertas_bp, init_alertas_routes
from routes.reinicios_api import reinicios_bp, init_reinicios_routes
from monitoring import alert_mailer
from monitoring.incident_detector import IncidentDetector
from monitoring.tasy_host_monitor import TasyHostMonitor
from monitoring.restart_scheduler import RestartScheduler
from core.database import Database
from core import auth as auth_mod

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
    # static_folder/static_url_path explícitos: o padrão do Flask resolve
    # 'static' relativo a este arquivo (core/app.py), ou seja core/static,
    # que não existe. A pasta real do build (index.html, css, assets do
    # React) fica em server/static, um nível acima de core/.
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app = Flask(__name__, static_folder=os.path.join(base_dir, 'static'), static_url_path='/static')
    
    # Carregar configurações do config.py
    from core.config import config
    app.config.from_mapping(config.get_flask_config())

    # Configurar CORS
    CORS(app, resources={r"/*": config.get_cors_config()})
    
    # Inicializar SocketIO
    # async_mode='threading': usa threads nativas do Python — sem dependências externas,
    # compatível com Python 3.14+ (eventlet não suporta 3.14+ por mudanças em _thread).
    # ping_interval/ping_timeout explícitos: o servidor manda um ping a cada 25s
    # e só considera o cliente morto após 60s sem resposta. A folga maior (o
    # padrão é 20s) evita derrubar a sessão por uma oscilação curta de rede —
    # instabilidade momentânea deixa de virar desconexão. A detecção rápida de
    # conexão "muda" fica a cargo do watchdog no operador (~45s), do lado dele.
    socketio = SocketIO(
        app,
        cors_allowed_origins=config.get_cors_config()['origins'],
        async_mode='threading',
        ping_interval=25,
        ping_timeout=60,
        logger=False,
        engineio_logger=False,
    )
    
    # Inicializar Banco de Dados
    db = Database(db_path=config.database.path)
    
    # Dicionário para operadores conectados
    connected_operators = {}
    
    # ── Sessão de autenticação ──────────────────────────────────────────
    # A secret_key vem do config (persistida em server_config.json). O cookie é
    # HttpOnly por padrão no Flask; SameSite=Lax barra envio em requisições
    # cross-site, mitigando CSRF sem exigir token adicional.
    #
    # SESSION_COOKIE_SECURE fica desligado porque o servidor roda em HTTP na
    # rede interna do hospital. Ligar aqui faria o navegador descartar o cookie
    # e ninguém conseguiria entrar. Deve ser ativado junto com HTTPS.
    #
    # PERMANENT_SESSION_LIFETIME funciona como timeout por INATIVIDADE, não
    # como prazo fixo desde o login: SESSION_REFRESH_EACH_REQUEST (padrão do
    # Flask, não alterado aqui) reenvia o cookie com validade renovada a cada
    # requisição. Sem chamadas ao servidor por 2h, o cookie expira sozinho e a
    # próxima requisição cai em login_required.
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_NAME='tasy_sessao',
        PERMANENT_SESSION_LIFETIME=timedelta(hours=2),
    )

    # Registrar Blueprints
    app.register_blueprint(views_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(alertas_bp)
    app.register_blueprint(reinicios_bp)

    # Injetar dependências nos módulos
    init_api(db, socketio, connected_operators)
    init_alertas_routes(db)
    init_reinicios_routes(db)
    auth_mod.init_auth(db)

    # Camada de detecção de incidentes (isolada). Observa os eventos que o
    # servidor já recebe e alerta o plantão por e-mail quando percebe uma falha
    # generalizada. Não interfere no fluxo dos operadores.
    incident_detector = IncidentDetector(
        db_path=config.database.path,
        get_email_config=lambda: config.email,
        get_connected_ids=lambda: list(connected_operators.keys()),
        mailer=alert_mailer,
        logger=logger,
    )
    incident_detector.start()

    # Monitor direto do host do Tasy (sinal autoritativo de "Tasy caiu",
    # independente da quantidade de painéis). Camada isolada, thread própria.
    tasy_host_monitor = TasyHostMonitor(
        cfg=config.tasy_monitor,
        db_path=config.database.path,
        get_email_config=lambda: config.email,
        mailer=alert_mailer,
        logger=logger,
    )
    tasy_host_monitor.start()

    # Agendador dos reinícios automáticos dos painéis. Lê a programação salva
    # no banco (tela Configurações > Reinícios, só admin) e dispara o mesmo
    # comando que o botão manual do dashboard já usa — o agente não precisa
    # de nenhuma mudança para responder.
    restart_scheduler = RestartScheduler(
        db_path=config.database.path,
        socketio=socketio,
        connected_operators=connected_operators,
        logger=logger,
    )
    restart_scheduler.start()

    # Validação no boot: deixa explícito no log se os alertas estão realmente
    # prontos. Um erro de config não pode deixar o plantão desprotegido sem
    # ninguém perceber.
    try:
        from core.email_service import smtp_configurado
        n_dest = 0
        try:
            cur = db.conn.cursor()
            cur.execute("SELECT COUNT(*) FROM alertas_destinatarios WHERE ativo = 1")
            n_dest = cur.fetchone()[0]
        except Exception:
            pass
        smtp_ok = smtp_configurado(config.email)
        pronto = smtp_ok and n_dest > 0
        marca = "✅" if pronto else "⚠️"
        logger.info(f"{marca} Alertas: SMTP {'ok' if smtp_ok else 'NÃO configurado'}, "
                    f"{n_dest} destinatário(s) ativo(s), monitor de host "
                    f"{'ligado' if config.tasy_monitor.habilitado else 'desligado'}.")
        if not pronto:
            logger.warning("Alertas NÃO estão prontos para notificar o plantão — "
                           "verifique SMTP (TASY_SMTP_SENHA) e destinatários cadastrados.")
    except Exception as e:
        logger.warning(f"Falha na validação de alertas no boot: {e}")

    # Primeiro administrador: criado apenas quando não há nenhum usuário.
    # A senha é sorteada e mostrada uma única vez — nunca fica no código.
    caminho_aviso = os.path.join(os.path.dirname(config.database.path), 'PRIMEIRO_ACESSO.txt')
    auth_mod.garantir_admin_inicial(caminho_aviso)

    # Pedidos de redefinição vencidos há mais de 7 dias saem do banco a cada
    # partida. Não há rotina agendada no servidor, e o custo aqui é uma única
    # DELETE — melhor que deixar a tabela crescer indefinidamente.
    removidos = auth_mod.limpar_tokens_expirados()
    if removidos:
        logger.info(f"Pedidos de redefinição de senha vencidos removidos: {removidos}")

    init_auth_routes(caminho_aviso)
    register_websocket_handlers(socketio, db, connected_operators, logger,
                                incident_detector=incident_detector)
    
    logger.info("Aplicação Flask e dependências configuradas com sucesso.")
    
    return app, socketio, db