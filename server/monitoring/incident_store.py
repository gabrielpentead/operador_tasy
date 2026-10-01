# -*- coding: utf-8 -*-
"""
Persistência de incidentes de monitoramento (trilha de auditoria).

Guarda cada incidente (queda do host do Tasy, queda por unidade, painéis
instáveis) com abertura e recuperação pareadas. Serve para: auditoria, histórico
na tela e casar cada recuperação com sua abertura exata.

Usado pelo detector e pelo monitor de host, cada um com sua PRÓPRIA conexão
sqlite. `ensure_table` deixa o módulo autônomo (cria a tabela se faltar), então
funciona mesmo num banco recém-criado. Nunca levanta exceção para fora — no pior
caso, loga e segue (persistir é auxiliar; não pode atrapalhar o alerta em si).
"""

import json
import logging

logger = logging.getLogger("TasyServerCentral")

_DDL = """
CREATE TABLE IF NOT EXISTS incidentes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo TEXT NOT NULL,              -- 'tasy_host' | 'tasy_unidade' | 'paineis_instaveis'
    unidade TEXT,                    -- nulo para o host
    aberto_em TEXT NOT NULL,
    recuperado_em TEXT,              -- nulo enquanto aberto
    afetados INTEGER DEFAULT 0,
    detalhe TEXT                     -- JSON (nomes, host, etc.)
)
"""


def ensure_table(conn):
    try:
        conn.execute(_DDL)
        conn.commit()
    except Exception as e:
        logger.warning(f"incident_store: falha ao garantir tabela: {e}")


def registrar_aberto(conn, tipo, unidade, aberto_em, afetados=0, detalhe=None):
    """Insere um incidente aberto e devolve o id (ou None em falha)."""
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO incidentes (tipo, unidade, aberto_em, afetados, detalhe) "
            "VALUES (?, ?, ?, ?, ?)",
            (tipo, unidade, aberto_em, int(afetados or 0),
             json.dumps(detalhe, ensure_ascii=False) if detalhe is not None else None))
        conn.commit()
        return cur.lastrowid
    except Exception as e:
        logger.warning(f"incident_store: falha ao registrar abertura: {e}")
        return None


def registrar_recuperado(conn, incidente_id, recuperado_em):
    """Marca a recuperação do incidente."""
    if not incidente_id:
        return
    try:
        conn.execute("UPDATE incidentes SET recuperado_em = ? WHERE id = ?",
                     (recuperado_em, incidente_id))
        conn.commit()
    except Exception as e:
        logger.warning(f"incident_store: falha ao registrar recuperação: {e}")
