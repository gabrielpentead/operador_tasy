#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rotas de gerenciamento da programação de reinícios automáticos dos painéis
(somente admin).

CRUD sobre a tabela `reinicios_programados`. O disparo em si é feito pelo
monitoring/restart_scheduler.py, que só lê esta tabela; aqui é só o cadastro.
"""

import re
import logging
from flask import Blueprint, request, jsonify

from core import auth
from core.auth import admin_required

logger = logging.getLogger("TasyServerCentral")

reinicios_bp = Blueprint('reinicios', __name__, url_prefix='/api/reinicios')

_db = None

_RE_HORARIO = re.compile(r'^([01]\d|2[0-3]):([0-5]\d)$')
TARGETS_VALIDOS = ('ambos', 'monitor', 'totem')
DIAS_VALIDOS = set(range(7))  # 0=segunda .. 6=domingo


def init_reinicios_routes(db):
    global _db
    _db = db


def _serializar(r):
    return {
        'id': r['id'],
        'horario': r['horario'],
        'dias_semana': [int(p) for p in (r['dias_semana'] or '').split(',') if p.strip() != ''],
        'target': r['target'],
        'descricao': r.get('descricao') or '',
        'ativo': bool(r['ativo']),
        'disparado_em': r.get('disparado_em'),
    }


def _validar_dias_semana(valor):
    """Aceita lista de inteiros 0-6. Devolve (texto_para_o_banco, erro)."""
    if not isinstance(valor, list) or not valor:
        return None, 'Informe ao menos um dia da semana'
    try:
        dias = {int(d) for d in valor}
    except (TypeError, ValueError):
        return None, 'Dias da semana inválidos'
    if not dias.issubset(DIAS_VALIDOS):
        return None, 'Dias da semana inválidos'
    return ','.join(str(d) for d in sorted(dias)), None


@reinicios_bp.route('', methods=['GET'])
@admin_required
def listar():
    return jsonify({'success': True,
                    'reinicios': [_serializar(r) for r in _db.listar_reinicios_programados()]})


@reinicios_bp.route('', methods=['POST'])
@admin_required
def criar():
    try:
        d = request.get_json(silent=True) or {}
        horario = (d.get('horario') or '').strip()
        target = (d.get('target') or 'ambos').strip()
        descricao = (d.get('descricao') or '').strip()

        if not _RE_HORARIO.match(horario):
            return jsonify({'success': False, 'error': 'Horário inválido. Use o formato HH:MM'}), 400
        if target not in TARGETS_VALIDOS:
            return jsonify({'success': False, 'error': 'Alvo inválido'}), 400

        dias_texto, erro = _validar_dias_semana(d.get('dias_semana'))
        if erro:
            return jsonify({'success': False, 'error': erro}), 400

        novo_id = _db.criar_reinicio_programado(
            horario, dias_texto, target=target, descricao=descricao or None,
            ativo=bool(d.get('ativo', True)))
        logger.info(f"Reinício programado criado ({horario}, alvo={target}) "
                    f"por '{auth.usuario_atual()['login']}'")
        return jsonify({'success': True, 'id': novo_id}), 201
    except Exception as e:
        logger.error(f"Erro ao criar reinício programado: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Erro interno'}), 500


@reinicios_bp.route('/<int:reinicio_id>', methods=['PUT'])
@admin_required
def editar(reinicio_id):
    try:
        if not _db.obter_reinicio_programado(reinicio_id):
            return jsonify({'success': False, 'error': 'Agendamento não encontrado'}), 404

        d = request.get_json(silent=True) or {}
        campos = {}

        if 'horario' in d:
            horario = (d.get('horario') or '').strip()
            if not _RE_HORARIO.match(horario):
                return jsonify({'success': False, 'error': 'Horário inválido. Use o formato HH:MM'}), 400
            campos['horario'] = horario

        if 'dias_semana' in d:
            dias_texto, erro = _validar_dias_semana(d.get('dias_semana'))
            if erro:
                return jsonify({'success': False, 'error': erro}), 400
            campos['dias_semana'] = dias_texto

        if 'target' in d:
            target = (d.get('target') or '').strip()
            if target not in TARGETS_VALIDOS:
                return jsonify({'success': False, 'error': 'Alvo inválido'}), 400
            campos['target'] = target

        if 'descricao' in d:
            campos['descricao'] = (d.get('descricao') or '').strip() or None

        if 'ativo' in d:
            campos['ativo'] = bool(d['ativo'])

        if not campos:
            return jsonify({'success': False, 'error': 'Nada para atualizar'}), 400

        _db.atualizar_reinicio_programado(reinicio_id, campos)
        logger.info(f"Reinício programado #{reinicio_id} atualizado "
                    f"por '{auth.usuario_atual()['login']}'")
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Erro ao editar reinício programado: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Erro interno'}), 500


@reinicios_bp.route('/<int:reinicio_id>', methods=['DELETE'])
@admin_required
def excluir(reinicio_id):
    try:
        _db.excluir_reinicio_programado(reinicio_id)
        logger.info(f"Reinício programado #{reinicio_id} removido "
                    f"por '{auth.usuario_atual()['login']}'")
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Erro ao excluir reinício programado: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Erro interno'}), 500
