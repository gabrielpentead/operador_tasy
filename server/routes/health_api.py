#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# server/routes/health_api.py
#
# ★ NOVO ARQUIVO — Endpoint /api/server/health para a Health Bar do dashboard.
# Registre este blueprint em app.py com:
#
#   from routes.health_api import health_bp
#   app.register_blueprint(health_bp)
#
# Não altera nenhum arquivo existente.

from flask import Blueprint, jsonify
import logging

logger = logging.getLogger("TasyServerCentral")
health_bp = Blueprint('health', __name__, url_prefix='/api/server')


def _safe_import():
    """Tenta importar psutil; retorna None se não disponível."""
    try:
        import psutil
        return psutil
    except ImportError:
        return None


@health_bp.route('/health', methods=['GET'])
def server_health():
    """
    Retorna métricas de saúde do servidor:
      - ram_percent   : uso de RAM em %
      - disk_percent  : uso do disco raiz em %
      - cpu_temp      : temperatura da CPU em °C (se disponível)
      - net_latency   : latência estimada em ms (ping interno ao loopback)
    
    Se psutil não estiver instalado, todos os valores são None.
    Instale com: pip install psutil
    """
    psutil = _safe_import()

    ram_percent  = None
    disk_percent = None
    cpu_temp     = None
    net_latency  = None

    if psutil:
        try:
            ram_percent = psutil.virtual_memory().percent
        except Exception:
            pass

        try:
            disk_percent = psutil.disk_usage('/').percent
        except Exception:
            try:
                # Windows: unidade C:\
                disk_percent = psutil.disk_usage('C:\\').percent
            except Exception:
                pass

        try:
            # Temperatura disponível em Linux/Mac com sensores
            temps = psutil.sensors_temperatures()
            if temps:
                for key in ('coretemp', 'cpu_thermal', 'k10temp', 'acpitz'):
                    if key in temps and temps[key]:
                        cpu_temp = temps[key][0].current
                        break
        except (AttributeError, Exception):
            pass

        # Latência: mede tempo de conectar ao loopback (estimativa rápida sem ICMP)
        try:
            import socket, time
            start = time.perf_counter()
            with socket.create_connection(('127.0.0.1', 80), timeout=0.1):
                pass
            net_latency = (time.perf_counter() - start) * 1000
        except Exception:
            # fallback: 0ms (servidor local sem porta 80 aberta = muito rápido)
            net_latency = 0.0

    return jsonify({
        'success':      True,
        'ram_percent':  ram_percent,
        'disk_percent': disk_percent,
        'cpu_temp':     cpu_temp,
        'net_latency':  net_latency,
    })
