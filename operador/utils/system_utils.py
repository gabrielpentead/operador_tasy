#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Utilitários do sistema para o Cliente Operador Tasy
"""

import os
import re
import sys
import uuid
import socket
import platform
import subprocess
from typing import Optional, Tuple, List
import logging
from screeninfo import get_monitors

logger = logging.getLogger("TasyOperador.SystemUtils")

def get_monitors_info():
    """Usa a biblioteca screeninfo para obter a geometria de todos os monitores."""
    try:
        monitors = get_monitors()
        if not monitors:
            raise Exception("Nenhum monitor encontrado")
        # Converte a lista de objetos Monitor para uma lista de dicionários
        return [m.__dict__ for m in monitors]
    except Exception as e:
        logger.error(f"Erro ao obter informações dos monitores com screeninfo: {e}")
        # Retorna um monitor padrão como fallback
        return [{'x': 0, 'y': 0, 'width': 1920, 'height': 1080}]

def _numero_display(monitor: dict) -> Optional[int]:
    """Extrai N de um name '\\\\.\\DISPLAYN'. None se o nome não identificar."""
    achado = re.search(r'DISPLAY(\d+)', str(monitor.get('name') or ''), re.IGNORECASE)
    return int(achado.group(1)) if achado else None


def _area_fisica(monitor: dict) -> int:
    """Área física da tela em mm², vinda do EDID. 0 se o monitor não informar."""
    try:
        largura = int(monitor.get('width_mm') or 0)
        altura = int(monitor.get('height_mm') or 0)
        return largura * altura if largura > 0 and altura > 0 else 0
    except (TypeError, ValueError):
        return 0


def resolve_monitor_indices(monitors: List[dict],
                            pref_totem: Optional[int] = None,
                            pref_painel: Optional[int] = None) -> Tuple[int, int]:
    """Decide qual índice de `monitors` cada automação usa. Retorna (totem, painel).

    A regra continua sendo a original — tela MAIOR para o painel de senhas,
    tela MENOR para o totem — mas medida em TAMANHO FÍSICO, não em pixels.

    Por que mudou: a comparação anterior usava width*height (pixels). Nos painéis
    reais as duas telas são 1920x1080, então dava empate perfeito e a atribuição
    passava a depender da ordem de enumeração do screeninfo — que varia de máquina
    para máquina. Medido em milímetros o empate desaparece: 23" contra 43" numa
    máquina, 15" contra 29" na outra.

    Cascata:
      1. Preferência explícita do config.ini (número do DISPLAY do Windows).
      2. Área física (mm², do EDID): menor = totem, maior = painel.
      3. Número do \\\\.\\DISPLAYn (menor = totem), quando o monitor não informa
         tamanho físico — driver genérico, KVM, extensor HDMI — ou quando empata.
      4. Posição (x, y), apenas para garantir um resultado determinístico.

    Nunca levanta exceção: em caso de falha devolve o comportamento antigo (0, 1).
    """
    try:
        if not monitors:
            return 0, 0
        if len(monitors) == 1:
            return 0, 0

        por_display = {}
        for i, m in enumerate(monitors):
            n = _numero_display(m)
            if n is not None and n not in por_display:
                por_display[n] = i

        idx_totem = por_display.get(pref_totem) if pref_totem else None
        idx_painel = por_display.get(pref_painel) if pref_painel else None

        areas = [_area_fisica(m) for m in monitors]
        if all(a > 0 for a in areas) and len(set(areas)) == len(areas):
            ordem = sorted(range(len(monitors)), key=lambda i: areas[i])
            criterio = "tamanho físico (mm²)"
        elif len(por_display) == len(monitors):
            ordem = [por_display[k] for k in sorted(por_display)]
            criterio = "número do DISPLAY"
        else:
            ordem = sorted(range(len(monitors)),
                           key=lambda i: (monitors[i].get('x', 0), monitors[i].get('y', 0)))
            criterio = "posição (x,y)"

        if idx_totem is None:
            idx_totem = ordem[0]      # menor tela
        if idx_painel is None:
            idx_painel = ordem[-1]    # maior tela
        if idx_totem == idx_painel:
            outro = next((i for i in ordem if i != idx_totem), None)
            if outro is not None:
                idx_painel = outro

        def _descreve(i):
            m = monitors[i]
            mm = _area_fisica(m)
            pol = ((int(m.get('width_mm') or 0) ** 2 + int(m.get('height_mm') or 0) ** 2) ** 0.5) / 25.4
            tam = f", ~{pol:.0f}\"" if mm else ", tamanho não informado"
            return (f"idx {i} ({m.get('name')}, {m.get('width')}x{m.get('height')}"
                    f" em {m.get('x')},{m.get('y')}{tam})")

        logger.info(f"🖥️ Monitores por '{criterio}' — "
                    f"Totem → {_descreve(idx_totem)} | "
                    f"Painel → {_descreve(idx_painel)}")
        return idx_totem, idx_painel

    except Exception as e:
        logger.error(f"Falha ao resolver monitores, usando padrão (0, 1). Erro: {e}")
        return 0, (1 if len(monitors) > 1 else 0)


def get_hostname() -> str:
    """Retorna o hostname da máquina"""
    try:
        return socket.gethostname()
    except Exception as e:
        logger.error(f"Erro ao obter hostname: {e}")
        return "UNKNOWN"

def get_system_info() -> dict:
    """Retorna informações do sistema como um dicionário"""
    try:
        return {
            "hostname": socket.gethostname(),
            "os": f"{platform.system()} {platform.release()}"
        }
    except Exception as e:
        logger.error(f"Erro ao obter informações do sistema: {e}")
        return {"hostname": "UNKNOWN", "os": "UNKNOWN"}

def generate_operator_id() -> str:
    """Gera um ID único para o operador"""
    try:
        return str(uuid.uuid4())
    except Exception as e:
        logger.error(f"Erro ao gerar ID do operador: {e}")
        return f"operador-{get_hostname()}-{uuid.uuid4().hex[:8]}"

def check_edge_installed() -> bool:
    """Verifica se o Microsoft Edge está instalado"""
    try:
        if platform.system() == "Windows":
            # Verificar caminhos comuns do Edge
            edge_paths = [
                r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            ]
            
            for path in edge_paths:
                if os.path.exists(path):
                    logger.info(f"Microsoft Edge encontrado em: {path}")
                    return True
            
            # Tentar via registro do Windows
            try:
                import winreg
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 
                                   r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe")
                path = winreg.QueryValueEx(key, "")[0]
                winreg.CloseKey(key)
                if os.path.exists(path):
                    logger.info(f"Microsoft Edge encontrado via registro: {path}")
                    return True
            except:
                pass
        
        logger.warning("Microsoft Edge não encontrado")
        return False
        
    except Exception as e:
        logger.error(f"Erro ao verificar instalação do Edge: {e}")
        return False

def kill_edge_processes():
    """Mata todos os processos do Microsoft Edge"""
    try:
        if platform.system() == "Windows":
            subprocess.run(["taskkill", "/f", "/im", "msedge.exe"], 
                         capture_output=True, check=False)
            subprocess.run(["taskkill", "/f", "/im", "msedgedriver.exe"], 
                         capture_output=True, check=False)
            logger.info("Processos Edge terminados")
        else:
            subprocess.run(["pkill", "-f", "msedge"], check=False)
            logger.info("Processos Edge terminados")
    except Exception as e:
        logger.error(f"Erro ao terminar processos Edge: {e}")

def reset_application_data(config_path: str):
    """
    Reseta os dados da aplicação:
    1. Remove o arquivo de configuração (config.ini).
    2. Mata processos relacionados (se necessário).
    """
    try:
        # 1. Remove config.ini
        if os.path.exists(config_path):
            os.remove(config_path)
            logger.info(f"Arquivo de configuração removido: {config_path}")
        else:
            logger.warning(f"Arquivo de configuração não encontrado para remoção: {config_path}")
            
        # 2. Matar processos do Edge (garantir limpeza)
        kill_edge_processes()
        
        logger.info("Dados da aplicação resetados com sucesso.")
        return True
    except Exception as e:
        logger.error(f"Erro ao resetar dados da aplicação: {e}")
        return False

def is_admin() -> bool:
    """Verifica se o script está rodando como administrador"""
    try:
        if platform.system() == "Windows":
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        else:
            return os.geteuid() == 0
    except Exception:
        return False

def get_application_directory() -> str:
    """Retorna o diretório da aplicação"""
    if getattr(sys, 'frozen', False):
        # Executando como aplicativo compilado
        return os.path.dirname(sys.executable)
    else:
        # Executando como script Python
        return os.path.dirname(os.path.abspath(__file__))
