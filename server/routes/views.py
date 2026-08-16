#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# server/routes/views.py - Rotas para renderização das views

from flask import Blueprint, render_template, redirect
import logging

# Logger
logger = logging.getLogger("TasyServerCentral")

# Blueprint de views
views_bp = Blueprint('views', __name__)

@views_bp.route('/')
def index():
    """Página inicial - Dashboard"""
    logger.info("Acesso à página inicial")
    return render_template('index.html')

# Redirecionar /operadores para a página principal (dashboard)
@views_bp.route('/operadores')
def operadores_redirect():
    """Redireciona à página principal"""
    logger.info("Redirecionando para a página principal")
    return redirect('/') 