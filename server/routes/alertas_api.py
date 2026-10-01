#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rotas de gerenciamento dos destinatários de alertas críticos (somente admin).

CRUD simples sobre a tabela `alertas_destinatarios` + um envio de teste. Os
alertas em si são disparados pela camada de monitoramento (incident_detector);
aqui é só o cadastro de quem recebe.
"""

import logging
from flask import Blueprint, request, jsonify

from core.config import config
from core import auth
from core.auth import admin_required
from monitoring import alert_mailer

logger = logging.getLogger("TasyServerCentral")

alertas_bp = Blueprint('alertas', __name__, url_prefix='/api/alertas')

_db = None


def init_alertas_routes(db):
    global _db
    _db = db


def _serializar(d):
    return {
        'id': d['id'],
        'nome': d.get('nome') or '',
        'email': d['email'],
        'ativo': bool(d['ativo']),
        'recebe_critico': bool(d['recebe_critico']),
    }


@alertas_bp.route('/destinatarios', methods=['GET'])
@admin_required
def listar():
    return jsonify({'success': True,
                    'destinatarios': [_serializar(d) for d in _db.listar_destinatarios_alerta()]})


@alertas_bp.route('/destinatarios', methods=['POST'])
@admin_required
def criar():
    try:
        d = request.get_json(silent=True) or {}
        nome = (d.get('nome') or '').strip()
        email = (d.get('email') or '').strip().lower()

        if not email or not auth.email_valido(email):
            return jsonify({'success': False, 'error': 'Informe um e-mail válido'}), 400
        if _db.buscar_destinatario_alerta_por_email(email):
            return jsonify({'success': False, 'error': 'Este e-mail já está cadastrado'}), 409

        novo_id = _db.criar_destinatario_alerta(
            nome, email,
            ativo=bool(d.get('ativo', True)),
            recebe_critico=bool(d.get('recebe_critico', True)))
        logger.info(f"Destinatário de alerta criado: {email} por '{auth.usuario_atual()['login']}'")
        return jsonify({'success': True, 'id': novo_id}), 201
    except Exception as e:
        logger.error(f"Erro ao criar destinatário de alerta: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Erro interno'}), 500


@alertas_bp.route('/destinatarios/<int:dest_id>', methods=['PUT'])
@admin_required
def editar(dest_id):
    try:
        d = request.get_json(silent=True) or {}
        campos = {}
        if 'nome' in d:
            campos['nome'] = (d.get('nome') or '').strip()
        if 'email' in d:
            email = (d.get('email') or '').strip().lower()
            if not email or not auth.email_valido(email):
                return jsonify({'success': False, 'error': 'E-mail inválido'}), 400
            existente = _db.buscar_destinatario_alerta_por_email(email)
            if existente and existente['id'] != dest_id:
                return jsonify({'success': False, 'error': 'Este e-mail já está cadastrado'}), 409
            campos['email'] = email
        if 'ativo' in d:
            campos['ativo'] = bool(d['ativo'])
        if 'recebe_critico' in d:
            campos['recebe_critico'] = bool(d['recebe_critico'])

        if not campos:
            return jsonify({'success': False, 'error': 'Nada para atualizar'}), 400
        _db.atualizar_destinatario_alerta(dest_id, campos)
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Erro ao editar destinatário de alerta: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Erro interno'}), 500


@alertas_bp.route('/destinatarios/<int:dest_id>', methods=['DELETE'])
@admin_required
def excluir(dest_id):
    try:
        _db.excluir_destinatario_alerta(dest_id)
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Erro ao excluir destinatário de alerta: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Erro interno'}), 500


@alertas_bp.route('/testar', methods=['POST'])
@admin_required
def testar():
    """Dispara um e-mail de teste para os destinatários críticos ativos."""
    try:
        enviados = alert_mailer.enviar_teste(config.email, config.database.path)
        if enviados:
            return jsonify({'success': True, 'mensagem': f'E-mail de teste enviado ({enviados}).'})
        return jsonify({'success': False,
                        'error': 'Nada enviado. Verifique o SMTP e se há destinatário ativo.'}), 400
    except Exception as e:
        logger.error(f"Erro ao enviar e-mail de teste: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Erro interno'}), 500
