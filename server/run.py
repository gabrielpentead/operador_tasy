#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# server/run.py - Script para executar o servidor central

# eventlet removido: incompatível com Python 3.14+
# async_mode='threading' não requer monkey-patch nem dependência externa.

import os
import sys
import signal
import argparse
import logging
import socket
from pathlib import Path
from datetime import datetime

# --- Lógica do Banner ---
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

VERSION = "1.3.6"

def exibir_banner():
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        return
    versao = f"v{VERSION}"
    hoje = datetime.now().strftime("%d/%m/%Y")
    banner = f"""
{Colors.GREEN}{Colors.BOLD}╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║  {Colors.CYAN}██╗  ██╗███████╗██╗   ██╗                                   {Colors.GREEN}║
║  {Colors.CYAN}██║  ██║██╔════╝██║   ██║                                   {Colors.GREEN}║
║  {Colors.CYAN}███████║███████╗██║   ██║                                   {Colors.GREEN}║
║  {Colors.CYAN}██╔══██║╚════██║╚██╗ ██╔╝                                   {Colors.GREEN}║
║  {Colors.CYAN}██║  ██║███████║ ╚████╔╝                                    {Colors.GREEN}║
║  {Colors.CYAN}╚═╝  ╚═╝╚══════╝  ╚═══╝                                     {Colors.GREEN}║
║                                                              ║
║  {Colors.YELLOW}Central de Operadores - Painel Chamado de Senhas Tasy       {Colors.GREEN}║
║  {Colors.GREEN}{versao}{Colors.END}{Colors.GREEN}{' ' * (54 - len(versao) - len(hoje))}{hoje}      ║
╚══════════════════════════════════════════════════════════════╝{Colors.END}
    """
    print(banner)
# --- Fim do Banner ---

# Garantir imports corretos
sys.path.append(str(Path(__file__).parent))

# Importar aplicação
from app import create_app
from config import config

logger = logging.getLogger("TasyServerCentral")
logging.basicConfig(level=logging.INFO)

def is_port_in_use(port: int, host: str) -> bool:
    """Verifica se uma porta TCP está em uso."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((host, port)) == 0

def main():
    exibir_banner()

    parser = argparse.ArgumentParser(
        description="Servidor Central - Painel de Senhas HSV"
    )
    parser.add_argument(
        '--host',
        type=str,
        default=config.server.host,
        help=f"Host do servidor (padrão: {config.server.host})"
    )
    parser.add_argument(
        '--port',
        type=int,
        default=config.server.port,
        help=f"Porta do servidor (padrão: {config.server.port})"
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help="Ativar modo debug"
    )

    args = parser.parse_args()

    if args.debug:
        config.server.debug = True
        logging.getLogger().setLevel(logging.DEBUG)
        logger.info("Modo debug ativado.")

    if not os.environ.get('WERKZEUG_RUN_MAIN'):
        if is_port_in_use(args.port, args.host):
            logger.error(
                f"A porta {args.port} já está em uso em {args.host}"
            )
            return 1

    app, socketio, db = create_app()

    def signal_handler(sig, frame):
        print()
        logger.info("🛑 Encerrando servidor...")
        try:
            if db:
                if hasattr(db, 'session'):
                    db.session.remove()
                if hasattr(db, 'close'):
                    db.close()
        except Exception as e:
            logger.warning(f"Erro ao fechar recursos: {e}")

        logger.info("👋 Servidor encerrado.")
        os._exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info(f"Iniciando servidor em http://{args.host}:{args.port}")
    logger.info(
        f"Ambiente: {'Desenvolvimento' if config.server.debug else 'Produção'}"
    )
    print("-" * 60)

    socketio.run(
        app,
        host=args.host,
        port=args.port,
        debug=config.server.debug,
        use_reloader=config.server.debug
    )

    return 0

if __name__ == '__main__':
    sys.exit(main())
