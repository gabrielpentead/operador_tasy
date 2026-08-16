#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🏥 CLIENTE OPERADOR TASY - VERSÃO MODULAR
Hospital São Vicente - Painel de Senhas HSV

Entry point principal que usa a nova arquitetura modular com interface Textual.

Autor: Núcleo de Tecnologia da Informação - Hospital São Vicente
Data: 21/04/2026
Versão: 1.5.2
"""

import sys
import os
import time
import logging
import threading
import traceback
from pathlib import Path

# Garantir que o diretório atual está no path para imports
current_dir = Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

# Importar os componentes da nova arquitetura
from core.logging_setup import setup_logging
from core.config import OperadorConfig
from core.client import OperadorClient
from utils.constants import VERSION, HOSTNAME, SYSTEM_INFO
from utils.system_utils import check_edge_installed

# Importar a nova app Textual (console_ui agora é uma instância de App)
from core.console_ui import console_ui

def main():
    """Função principal que inicializa e executa o cliente modular."""
    try:
        # Variável para referência do cliente (para cleanup)
        client_ref = {"instance": None}
        
        # 1. Carregar Configurações
        config = OperadorConfig()
        log_level = config.get_log_level()

        # 2. Configurar Logging
        # O setup_logging configura o TextualLogHandler que aponta para console_ui
        logger = setup_logging(log_level)
        
        print("\n🚀 INICIANDO CLIENTE OPERADOR TASY...")
        print("   - Carregando configurações...")
        
        # 3. Verificar e realizar registro interativo (modo CLI) ANTES de iniciar a TUI
        # Isso evita que o input() bloqueie a interface gráfica ou fique invisível
        temp_client = OperadorClient(config)
        if not temp_client._ensure_operator_registered():
            print("❌ Registro do operador falhou ou foi cancelado.")
            return 1
        
        print("   - Verificando dependências e drivers (isso pode levar alguns instantes)...")
        # Limpar a tela do terminal após registro para dar lugar à TUI
        # os.system('cls' if os.name == 'nt' else 'clear') # Removido para manter o feedback visual do boot por enquanto

        # 4. Definir a lógica de negócio (Cliente) para rodar em thread separada
        def run_client_logic():
            # Pequena pausa para garantir que a TUI montou e está pronta para receber logs
            time.sleep(1.5)
            
            logger.info("🚀 Interface Gráfica Iniciada.")
            logger.info("🔄 Iniciando lógica do cliente...")
            
            # Verificar Dependências Críticas (Logging agora vai para a TUI)
            logger.info("🔍 Verificando pré-requisitos do sistema...")
            if not check_edge_installed():
                logger.error("❌ Microsoft Edge não foi encontrado! Instale-o para continuar.")
                # Manter a mensagem visível por um tempo antes de encerrar (se implementado)
                time.sleep(5)
                return

            logger.info("✅ Pré-requisitos verificados com sucesso.")

            try:
                # O cliente já está registrado (garantido pelo passo 3)
                # Usamos a instância existente ou criamos uma nova limpa, mas com a config atualizada
                cliente = OperadorClient(config)
                client_ref["instance"] = cliente
                
                # Injetar gerenciador de UI no cliente (console_ui é a App Textual agora)
                # A App tem o método update_data compatível
                cliente.ui_manager = console_ui 
                
                # Executar loop principal do cliente (Bloqueante nesta thread)
                cliente.run()
            except Exception as e:
                logger.critical(f"❌ Erro fatal na thread do cliente: {e}", exc_info=True)

        # 5. Iniciar Thread de Negócio
        client_thread = threading.Thread(target=run_client_logic, name="ClientThread", daemon=True)
        client_thread.start()

        # 6. Iniciar Interface Rica (Bloqueia a thread principal)
        console_ui.run()
        
        # 7. Graceful Shutdown após fechar a UI
        print("\n🛑 Encerrando aplicação...")
        if client_ref["instance"]:
            print("   - Parando automação e fechando navegadores...")
            client_ref["instance"]._cleanup()
            print("   - Recursos liberados.")
        
        return 0
            
    except ImportError as e:
        print(f"\n❌ ERRO DE IMPORTAÇÃO: {e}")
        print("   Verifique se todas as dependências (incluindo 'textual') estão instaladas.")
        input("   Pressione Enter para sair...")
        return 1
    except KeyboardInterrupt:
        return 0
    except Exception as e:
        try:
            logging.getLogger("TasyOperador").critical(f"Erro fatal na inicialização: {e}", exc_info=True)
        except:
            pass
            
        print(f"\n❌ ERRO CRÍTICO INESPERADO: {e}")
        print("\n🔍 Detalhes do erro (Traceback):")
        traceback.print_exc()
        
        print("\n   Consulte o arquivo de log para mais detalhes.")
        input("   Pressione Enter para sair...")
        return 1

if __name__ == "__main__":
    sys.exit(main())
