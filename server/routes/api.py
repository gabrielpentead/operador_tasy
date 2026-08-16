#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# server/routes/api.py - Rotas de API para gerenciamento de operadores

from flask import Blueprint, request, jsonify
import logging
from config import config

# Logger
logger = logging.getLogger("TasyServerCentral")

# Blueprint de API
api_bp = Blueprint('api', __name__, url_prefix='/api')

# Referências (serão injetadas)
db = None
socketio = None
connected_operators = None

def init_api(database, socket_io, operators):
    """Inicializa as referências necessárias para o módulo de API"""
    global db, socketio, connected_operators
    db = database
    socketio = socket_io
    connected_operators = operators

@api_bp.route('/operadores', methods=['GET'])
def get_operadores():
    """Retorna a lista de todos os operadores cadastrados"""
    try:
        operadores = db.get_all_operadores()
        for op in operadores:
            op['online'] = op.get('id') in connected_operators
            if op['online']:
                op_data = connected_operators[op.get('id')]
                op['status'] = op_data.get('status', 'Conectado')
                op['ultima_atualizacao'] = op_data.get('ultima_atualizacao')
                op['hostname'] = op_data.get('system_info', {}).get('hostname')
                op['ip'] = op_data.get('ip')
                op['saude'] = op_data.get('saude')
                op['nivel_saude'] = op_data.get('nivel_saude', 'Normal')
        return jsonify({'success': True, 'operadores': operadores})
    except Exception as e:
        logger.error(f"Erro ao obter operadores: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/operadores', methods=['POST'])
def add_operador():
    """Adiciona um novo operador"""
    try:
        data = request.json
        if not data.get('nome') or not data.get('tipo_cadastro'):
            return jsonify({'success': False, 'error': 'Campos essenciais (nome, tipo_cadastro) são obrigatórios.'}), 400

        operador_id = db.add_operador(data)
        
        socketio.emit('operador_adicionado', {'id': operador_id, 'nome': data.get('nome')})
        return jsonify({'success': True, 'id': operador_id}), 201
    except Exception as e:
        logger.error(f"Erro ao adicionar operador: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/operadores/<operador_id>', methods=['GET'])
def get_operador(operador_id):
    """Obtém informações de um operador específico"""
    try:
        operador = db.get_operador(operador_id)
        if not operador:
            return jsonify({'success': False, 'error': 'Operador não encontrado'}), 404
        
        operador['online'] = operador_id in connected_operators
        if operador['online']:
            op_data = connected_operators[operador_id]
            operador['status'] = op_data.get('status', 'Conectado')
            operador['ultima_atualizacao'] = op_data.get('ultima_atualizacao')
            operador['hostname'] = op_data.get('system_info', {}).get('hostname')
            operador['ip'] = op_data.get('ip')

        return jsonify({'success': True, 'operador': operador})
    except Exception as e:
        logger.error(f"Erro ao obter operador: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/operadores/<operador_id>', methods=['PUT'])
def update_operador(operador_id):
    """Atualiza as informações de um operador"""
    try:
        data = request.json
        if not db.get_operador(operador_id):
            return jsonify({'success': False, 'error': 'Operador não encontrado'}), 404

        db.update_operador(operador_id, data)

        if operador_id in connected_operators:
            operador_atualizado = db.get_operador(operador_id)
            config_payload = {key: operador_atualizado.get(key) for key in operador_atualizado.keys()}
            config_payload['reiniciar_automacao'] = True
            
            socketio.emit('config_atualizada', config_payload, room=operador_id)
            logger.info(f"Configurações atualizadas enviadas para o operador {operador_id}")

        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Erro ao atualizar operador: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/operadores/<operador_id>', methods=['DELETE'])
def delete_operador(operador_id):
    """Remove um operador"""
    try:
        if not db.get_operador(operador_id):
            return jsonify({'success': False, 'error': 'Operador não encontrado'}), 404
        
        # Enviar comando de reset antes de remover
        if operador_id in connected_operators:
            socketio.emit('comando_reset', {'mensagem': 'Operador excluído pelo administrador.'}, room=operador_id)
            logger.info(f"Comando de RESET enviado para operador {operador_id} antes da exclusão.")
        
        db.delete_operador(operador_id)
        
        # A desconexão forçada pode não ser necessária se o cliente resetar, 
        # mas mantemos como fallback após um breve delay se fosse assíncrono, 
        # aqui o cliente deve processar o reset.
        if operador_id in connected_operators:
            socketio.emit('desconectar', room=operador_id)
            
        socketio.emit('operador_removido', {'id': operador_id})
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Erro ao remover operador: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/operadores/<operador_id>/comando', methods=['POST'])
def enviar_comando(operador_id):
    """Envia um comando para um operador específico"""
    try:
        data = request.json
        comando = data.get('comando')
        target = data.get('target', 'ambos')
        
        if not comando or comando not in ['iniciar', 'parar', 'reiniciar']:
            return jsonify({'success': False, 'error': 'Comando inválido'}), 400
        
        if operador_id not in connected_operators:
            return jsonify({'success': False, 'error': 'Operador offline'}), 400
        
        payload = {'comando': comando, 'target': target}
        socketio.emit('comando', payload, room=operador_id)
        logger.info(f"Comando '{comando}' (alvo: {target}) enviado para operador {operador_id}")
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Erro ao enviar comando: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/servidor/config', methods=['GET'])
def get_server_config():
    """Retorna a configuração atual do servidor."""
    try:
        return jsonify({
            'success': True,
            'config': {
                'host': config.server.host,
                'port': config.server.port
            }
        })
    except Exception as e:
        logger.error(f"Erro ao obter configuração do servidor: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


# ── Saúde do Servidor (Health Check) ─────────────────────────────────────────
import subprocess
import time

@api_bp.route('/servidor/saude', methods=['GET'])
def get_server_health():
    """
    Retorna métricas de saúde do servidor Ubuntu:
    RAM, Disco, Temperatura CPU e Latência de rede (ping gateway).
    Depende de: psutil  →  pip install psutil
    """
    try:
        import psutil

        # ── RAM ───────────────────────────────────────────────────────────────
        ram = psutil.virtual_memory()
        ram_total_gb  = round(ram.total  / (1024 ** 3), 1)
        ram_usado_gb  = round(ram.used   / (1024 ** 3), 1)
        ram_pct       = ram.percent

        # ── Disco (partição raiz) ─────────────────────────────────────────────
        disco = psutil.disk_usage('/')
        disco_total_gb = round(disco.total / (1024 ** 3), 1)
        disco_usado_gb = round(disco.used  / (1024 ** 3), 1)
        disco_pct      = disco.percent

        # ── Temperatura CPU ───────────────────────────────────────────────────
        temp_cpu = None
        try:
            temps = psutil.sensors_temperatures()
            # Tenta fontes comuns no Linux
            for fonte in ('coretemp', 'k10temp', 'cpu_thermal', 'acpitz'):
                if fonte in temps and temps[fonte]:
                    temp_cpu = round(temps[fonte][0].current, 1)
                    break
            # Fallback: primeira leitura disponível
            if temp_cpu is None and temps:
                primeira_fonte = next(iter(temps.values()))
                if primeira_fonte:
                    temp_cpu = round(primeira_fonte[0].current, 1)
        except Exception:
            pass

        # ── Latência de rede (ping gateway padrão) ────────────────────────────
        latencia_ms = None
        try:
            # Descobre o gateway padrão
            gw_result = subprocess.run(
                ['ip', 'route', 'show', 'default'],
                capture_output=True, text=True, timeout=3
            )
            gateway = None
            for parte in gw_result.stdout.split():
                if parte not in ('default', 'via', 'dev', 'proto', 'src', 'metric'):
                    # Primeiro token que parece IP após 'via'
                    import re
                    if re.match(r'^\d+\.\d+\.\d+\.\d+$', parte):
                        gateway = parte
                        break

            if gateway:
                t_inicio = time.time()
                ping = subprocess.run(
                    ['ping', '-c', '1', '-W', '2', gateway],
                    capture_output=True, text=True, timeout=5
                )
                if ping.returncode == 0:
                    latencia_ms = round((time.time() - t_inicio) * 1000, 1)
                    # Tenta extrair valor mais preciso do output do ping
                    import re as _re
                    m = _re.search(r'time=(\d+\.?\d*)\s*ms', ping.stdout)
                    if m:
                        latencia_ms = round(float(m.group(1)), 1)
        except Exception:
            pass

        # ── CPU geral ─────────────────────────────────────────────────────────
        cpu_pct = psutil.cpu_percent(interval=0.5)

        # ── Uptime do servidor ────────────────────────────────────────────────
        uptime_secs = int(time.time() - psutil.boot_time())
        uptime_dias  = uptime_secs // 86400
        uptime_horas = (uptime_secs % 86400) // 3600
        uptime_mins  = (uptime_secs % 3600) // 60
        uptime_str   = f"{uptime_dias}d {uptime_horas}h {uptime_mins}m"

        return jsonify({
            'success': True,
            'saude': {
                'ram': {
                    'usado_gb':  ram_usado_gb,
                    'total_gb':  ram_total_gb,
                    'percentual': ram_pct
                },
                'disco': {
                    'usado_gb':  disco_usado_gb,
                    'total_gb':  disco_total_gb,
                    'percentual': disco_pct
                },
                'temperatura_cpu': temp_cpu,
                'latencia_ms':     latencia_ms,
                'cpu_percentual':  cpu_pct,
                'uptime':          uptime_str,
            }
        })

    except ImportError:
        return jsonify({
            'success': False,
            'error': 'Biblioteca psutil não instalada. Execute: pip install psutil'
        }), 500
    except Exception as e:
        logger.error(f"Erro ao obter saúde do servidor: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500
