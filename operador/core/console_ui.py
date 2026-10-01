#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Módulo de Interface de Usuário (TUI) usando Textual.
Refatorado para corrigir layout Grid e incluir status detalhado do Tasy.
"""

import logging
import socket
import threading
import requests
from datetime import datetime
from typing import Dict, Any, Optional

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, Grid
from textual.widgets import Header, Footer, Log, Static, Label, Digits
from textual.reactive import reactive
from rich.text import Text
from rich.panel import Panel
from rich.align import Align

# Tentar importar psutil
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

def get_local_ip():
    try:
        return socket.gethostbyname(socket.gethostname())
    except:
        return "127.0.0.1"

def check_tasy_connection(url):
    """Verifica se o Tasy está acessível via requisição HTTP simples."""
    try:
        # Timeout curto para não bloquear
        response = requests.get(url, timeout=2, verify=False)
        return response.status_code == 200
    except:
        return False


# Alvo do indicador de status do Tasy (servidor interno).
TASY_HOST = "tasy.hospitalsaovicente.org.br"
TASY_PORT = 443

def check_tasy_online(host: str = TASY_HOST, port: int = TASY_PORT) -> bool:
    """Considera o Tasy 'online' se a porta web responder ao handshake TCP.

    Usa conexão TCP em vez de ping ICMP de propósito:
      - ICMP costuma ser bloqueado por firewall -> ping falha mesmo com o site no ar
        (era o que estava marcando offline falso);
      - um HTTP 503 do proxy ainda significa servidor no ar: o handshake TCP
        completa antes da camada HTTP, então conta corretamente como online.
    """
    try:
        with socket.create_connection((host, port), timeout=2):
            return True
    except Exception:
        return False

class ClientInfoWidget(Static):
    """Widget consolidado para exibir informações do cliente, sistema e conexões."""
    
    # Dados reativos
    client_info = reactive({"name": "...", "id": "...", "profile": "...", "description": "..."})
    connection_status = reactive({"server": False, "tasy_site": False, "internet": True})
    system_stats = reactive({"cpu": 0.0, "ram": 0.0})
    network_info = reactive({"ip_local": get_local_ip(), "server_ip": "..."})
    tasy_config = reactive({"user": "...", "url": "..."})

    def on_mount(self):
        # Atualiza estatísticas de sistema a cada 2s
        self.set_interval(2.0, self.update_stats)
        # Atualiza status de conexão do site Tasy a cada 10s
        self.set_interval(10.0, self.check_connections)

    def update_stats(self):
        if HAS_PSUTIL:
            try:
                self.system_stats = {
                    "cpu": psutil.cpu_percent(),
                    "ram": psutil.virtual_memory().percent
                }
            except: pass

    def check_connections(self):
        # Executar em thread para não bloquear UI
        threading.Thread(target=self._check_tasy_thread, daemon=True).start()

    def _check_tasy_thread(self):
        # Status via conexão TCP na porta 443 do host do Tasy.
        # Não usa ICMP (bloqueado por firewall) nem exige HTTP 200 (o proxy
        # devolve 503, mas o servidor está no ar).
        is_online = check_tasy_online()
        # Atualizar via call_from_thread é seguro
        self.app.call_from_thread(self._update_tasy_status, is_online)

    def _update_tasy_status(self, is_online):
        new_status = self.connection_status.copy()
        new_status['tasy_site'] = is_online
        self.connection_status = new_status

    def render(self):
        # Indicador de status
        def status_dot(active: bool) -> tuple:
            return ("● ", "green" if active else "red3")
        
        # Barra de progresso moderna e responsiva
        def progress_bar(label: str, value: float, width: int) -> Text:
            # Calcula largura da barra baseado no espaco disponivel
            # Reserva: 2 espacos iniciais + label(4) + espaco + barra + espaco + porcentagem(6)
            bar_width = max(6, width - 16)
            filled = int((value / 100) * bar_width)
            empty = bar_width - filled
            
            # Cores baseadas no uso
            if value < 50:
                color, bg_color = "green", "dark_green"
            elif value < 80:
                color, bg_color = "yellow", "olive"
            else:
                color, bg_color = "red", "dark_red"
            
            bar = Text()
            bar.append(f"  {label:<4} ", style="dim white")
            bar.append("▰" * filled, style=f"bold {color}")
            bar.append("▱" * empty, style="dim white")
            bar.append(f" {value:5.1f}%", style=f"bold {color}")
            return bar
        
        # Largura disponivel (usa o tamanho do widget)
        try:
            width = self.size.width - 4
        except:
            width = 38
        
        # Separador responsivo
        sep_width = min(width - 2, 40)
        separator = "─" * sep_width
        
        # Trunca texto de acordo com espaco disponivel
        max_text = max(10, width - 15)

        text = Text()
        
        # Secao Identificacao
        text.append(f" {separator}\n", style="dim cyan")
        text.append("  IDENTIFICAÇÃO\n", style="bold bright_cyan")
        text.append(f" {separator}\n", style="dim cyan")
        text.append("  Nome       ", style="dim white")
        text.append(f"{str(self.client_info.get('name', '...'))[:max_text]}\n", style="white")
        text.append("  Descrição", style="dim white")
        text.append(f"{str(self.client_info.get('description', '...'))[:max_text]}\n", style="white")
        text.append("  ID         ", style="dim white")
        text.append(f"{str(self.client_info.get('id', '...'))[:max_text]}\n", style="cyan")
        text.append("  Perfil     ", style="dim white")
        text.append(f"{self.client_info.get('profile', '...')}\n", style="white")
        
        # Secao Conexoes
        text.append("\n")
        text.append(f" {separator}\n", style="dim cyan")
        text.append("  CONEXÕES\n", style="bold bright_cyan")
        text.append(f" {separator}\n", style="dim cyan")
        text.append("  IP Local   ", style="dim white")
        text.append(f"{self.network_info['ip_local']}\n", style="white")
        text.append("  Server     ", style="dim white")
        text.append(f"{self.network_info['server_ip']}\n", style="white")
        text.append("  Servidor   ", style="dim white")
        text.append(*status_dot(self.connection_status['server']))
        text.append(f"{'Conectado' if self.connection_status['server'] else 'Offline'}\n", style="white")
        text.append("  Internet   ", style="dim white")
        text.append(*status_dot(self.connection_status['internet']))
        text.append(f"{'OK' if self.connection_status['internet'] else 'Falha'}\n", style="white")
        
        # Secao Tasy (destaque em magenta)
        text.append("\n")
        text.append(f" {separator}\n", style="dim magenta")
        text.append("  TASY\n", style="bold bright_magenta")
        text.append(f" {separator}\n", style="dim magenta")
        text.append("  Status     ", style="dim white")
        text.append(*status_dot(self.connection_status['tasy_site']))
        text.append(f"{'Online' if self.connection_status['tasy_site'] else 'Offline'}\n", style="white")
        text.append("  Usuario    ", style="dim white")
        text.append(f"{self.tasy_config.get('user', '...')}\n", style="white")
        
        # Secao Sistema (CPU/RAM)
        text.append("\n")
        text.append(f" {separator}\n", style="dim yellow")
        text.append("  SISTEMA\n", style="bold bright_yellow")
        text.append(f" {separator}\n", style="dim yellow")
        
        cpu_val = self.system_stats["cpu"]
        ram_val = self.system_stats["ram"]
        
        text.append_text(progress_bar("CPU", cpu_val, width))
        text.append("\n")
        text.append_text(progress_bar("RAM", ram_val, width))
        text.append("\n")

        return Panel(text, title="[bold]Painel de Controle[/bold]", border_style="bright_blue", padding=(0, 1))

class AutomationStatusWidget(Static):
    """Widget para exibir status das automações (Monitor/Totem)."""
    
    status_data = reactive({})

    def render(self):
        instances = {k: v for k, v in self.status_data.items() if k != 'connected'}
        
        if not instances:
            loading_text = Text()
            loading_text.append("\n")
            loading_text.append("  ◌ ", style="dim cyan")
            loading_text.append("Aguardando inicialização...\n\n", style="dim white")
            return Panel(loading_text, title="[bold]Automações[/bold]", border_style="bright_magenta", padding=(0, 1))
        
        text_content = Text()
        text_content.append("\n")
        
        for name, status in instances.items():
            is_running = status == "Executando" or "ativado" in str(status).lower()
            is_error = "Erro" in str(status)
            
            # Indicadores visuais limpos
            if is_running:
                icon, color = "▶", "green"
            elif is_error:
                icon, color = "✕", "red"
            else:
                icon, color = "○", "yellow"
            
            text_content.append(f"  {icon} ", style=color)
            text_content.append(f"{name.upper():<12}", style="bold white")
            text_content.append(f"{status}\n", style=color)
        
        text_content.append("\n")
            
        return Panel(text_content, title="[bold]Automações[/bold]", border_style="bright_magenta", padding=(0, 1))

class OperadorApp(App):
    """Aplicação Principal TUI"""

    CSS = """
    Screen {
        layout: grid;
        grid-size: 2 2;
        grid-columns: 1fr 2fr;
        grid-rows: 1fr 2fr;
        background: $surface;
    }

    #client_info {
        row-span: 2;
        height: 100%;
        min-width: 38;
        max-width: 50;
        margin: 1 0 1 1;
    }

    #automations {
        height: 100%;
        margin: 1 1 0 1;
    }

    #logs-container {
        height: 100%;
        margin: 1 1 1 1;
        border: round $primary-lighten-2;
        background: $surface;
        padding: 0 1;
    }

    Log {
        border: none;
        background: transparent;
        height: 1fr;
        overflow-x: hidden;
            scrollbar-size: 0 0;
    }
    
    .log-title {
        height: auto;
        padding: 1 0 0 0;
        text-style: bold;
        color: $text-muted;
    }
    """

    TITLE = "Automação da Continuidade Operacional de Painéis"
    SUB_TITLE = "v1.5.5"

    BINDINGS = [
        ("d", "toggle_dark", "Alternar Modo Escuro"),
        ("q", "quit", "Sair"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        
        # ORDEM DE INSERÇÃO IMPORTA NO GRID!
        # 1. Info/Sistema (Esquerda, deve ocupar Col 1, Row 1 e Row 2)
        yield ClientInfoWidget(id="client_info")
        
        # 2. Automações (Direita, Topo - Col 2, Row 1)
        yield AutomationStatusWidget(id="automations")

        # 3. Logs (Direita, Baixo - Col 2, Row 2)
        with Container(id="logs-container"):
             yield Label("Logs", classes="log-title")
             yield Log(id="log_output", highlight=True)

        yield Footer()

    def on_mount(self):
        self.log_widget = self.query_one("#log_output", Log)
        self.client_widget = self.query_one("#client_info", ClientInfoWidget)
        self.status_widget = self.query_one("#automations", AutomationStatusWidget)
        
        # Configura o root logger para capturar TUDO
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        
        # Adiciona nosso handler apenas se não estiver já
        has_textual_handler = any(isinstance(h, TextualLogHandler) for h in logger.handlers)
        if not has_textual_handler:
            handler = TextualLogHandler(self)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S')
            handler.setFormatter(formatter)
            logger.addHandler(handler)

    def update_data(self, status=None, logs=None, sys_info=None, client_details=None):
        """Método chamado pelo Client para atualizar a UI."""
        if status:
            server_conn = status.get('connected', False)
            self.call_from_thread(self._update_status, status, server_conn)
        
        if client_details:
            self.call_from_thread(self._update_client, client_details)

    def _update_status(self, status, server_connected):
        self.status_widget.status_data = status
        
        new_conn_status = self.client_widget.connection_status.copy()
        new_conn_status["server"] = server_connected
        
        self.client_widget.connection_status = new_conn_status

    def _update_client(self, details):
        self.client_widget.client_info = {
            "name": details.get("name", "..."),
            "id": details.get("id", "..."),
            "profile": details.get("profile", "..."),
            "description": details.get("description", "Monitoramento de Senhas")
        }
        
        if 'server_ip' in details:
            new_net = self.client_widget.network_info.copy()
            new_net["server_ip"] = details['server_ip']
            self.client_widget.network_info = new_net

        self.client_widget.tasy_config = {
            "user": details.get('tasy_user', '...'),
            "url": details.get('tasy_url', 'https://tasy.hospitalsaovicente.org.br/#/')
        }

    def log_message(self, message: str):
        """Escreve no log (thread-safe)."""
        # write_line adiciona nova linha automaticamente e faz auto-scroll
        self.call_from_thread(self.log_widget.write_line, message)

# Singleton global
console_ui = OperadorApp()

class TextualLogHandler(logging.Handler):
    """Handler para redirecionar logs para o widget Log do Textual."""
    
    def __init__(self, app_instance: OperadorApp):
        super().__init__()
        self.app = app_instance
        
    def emit(self, record):
        try:
            msg = self.format(record)
            if self.app.is_running:
                self.app.log_message(msg)
        except Exception:
            self.handleError(record)