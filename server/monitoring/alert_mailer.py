# -*- coding: utf-8 -*-
"""
Montagem e envio dos e-mails de alerta de incidente.

Roda no worker do detector (fora da thread do WebSocket). Lê os destinatários
do banco (conexão própria) e usa o email_service já existente. Nunca levanta
exceção para fora — no pior caso, loga e segue.
"""

import time
import sqlite3
import logging
import threading
from datetime import datetime

from core.email_service import enviar_email_multi, smtp_configurado

logger = logging.getLogger("TasyServerCentral")

# Teto anti-enxurrada: mesmo com o debounce dos detectores, um cenário
# patológico (flapping) não pode inundar a caixa do plantão. Cinto de segurança.
_MAX_EMAILS_JANELA = 12
_JANELA_S = 600                # 10 min
_historico_envios = []
_trava_flood = threading.Lock()


def _sob_teto() -> bool:
    """Registra o envio e diz se ainda está dentro do teto (True = pode enviar)."""
    agora = time.monotonic()
    with _trava_flood:
        _historico_envios[:] = [t for t in _historico_envios if agora - t < _JANELA_S]
        if len(_historico_envios) >= _MAX_EMAILS_JANELA:
            return False
        _historico_envios.append(agora)
        return True


def _destinatarios_criticos(db_path):
    """E-mails ativos que recebem os alertas. 'Ativo' já basta: pausar ou
    excluir é a forma de não receber (a coluna recebe_critico fica reservada
    para uma eventual separação futura de tipos de alerta)."""
    try:
        con = sqlite3.connect(db_path)
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "SELECT email FROM alertas_destinatarios WHERE ativo = 1"
        ).fetchall()
        con.close()
        return [r['email'] for r in rows if r['email']]
    except Exception as e:
        logger.warning(f"Alertas: não foi possível ler destinatários: {e}")
        return []


def _lista_afetados(nomes, limite=15):
    if not nomes:
        return ''
    if len(nomes) <= limite:
        return '\n'.join(f"  • {n}" for n in nomes)
    visiveis = '\n'.join(f"  • {n}" for n in nomes[:limite])
    return f"{visiveis}\n  • … e mais {len(nomes) - limite}"


def _enviar_para_todos(cfg, db_path, assunto, texto, html):
    if not smtp_configurado(cfg):
        logger.error("Alerta de incidente NÃO enviado: SMTP não configurado.")
        return 0
    destinos = _destinatarios_criticos(db_path)
    if not destinos:
        logger.warning("Alerta de incidente sem destinatários ativos — nada enviado.")
        return 0
    if not _sob_teto():
        logger.error(f"Alerta SUPRIMIDO pelo teto anti-enxurrada "
                     f"(>{_MAX_EMAILS_JANELA} e-mails em {_JANELA_S//60} min): {assunto}")
        return 0
    # Um único envio (BCC) para todos, com retry. Entrega confiável e um
    # destinatário não vê o e-mail dos outros.
    enviados, err = enviar_email_multi(cfg, destinos, assunto, texto, html)
    if enviados:
        logger.info(f"Alerta enviado a {enviados} destinatário(s): {assunto}")
    else:
        logger.error(f"Alerta NÃO enviado ({err}): {assunto}")
    return enviados


def _corpo_txt(intro, pares, paineis=None, o_que_fazer=None):
    """Monta a versão em texto puro num tom natural e consistente."""
    partes = [intro, '', 'Resumo:']
    partes += [f"  • {k}: {v}" for k, v in pares]
    if paineis:
        partes += ['', 'Painéis envolvidos:', paineis]
    if o_que_fazer:
        partes += ['', o_que_fazer]
    partes += ['', '— Central de Operadores · monitoramento automático. '
                   'Não é preciso responder este e-mail.']
    return '\n'.join(partes)


def _card_html(cor, faixa, titulo, linhas_html, rodape=''):
    linhas = ''.join(f"<tr><td style='padding:4px 0;color:#586274;'>{k}</td>"
                     f"<td style='padding:4px 0;text-align:right;font-weight:600;'>{v}</td></tr>"
                     for k, v in linhas_html)
    return f"""<!doctype html><html lang="pt-BR"><body style="margin:0;padding:24px;
      background:#f5f7f6;font-family:'Segoe UI',Roboto,Arial,sans-serif;color:#212529;">
      <div style="max-width:560px;margin:0 auto;background:#fff;border-radius:8px;overflow:hidden;
           box-shadow:0 2px 8px rgba(0,0,0,.08);">
        <div style="background:{cor};color:#fff;padding:16px 24px;font-size:16px;font-weight:700;">
          {faixa}
        </div>
        <div style="padding:24px;">
          <p style="margin:0 0 16px;font-size:15px;">{titulo}</p>
          <table style="width:100%;border-collapse:collapse;font-size:14px;">{linhas}</table>
          {f'<p style="margin:16px 0 0;font-size:13px;color:#586274;">{rodape}</p>' if rodape else ''}
        </div>
        <div style="padding:12px 24px;background:#f5f7f6;font-size:11px;color:#8592a3;
             border-top:1px solid #dee2e6;">
          Central de Operadores — Hospital São Vicente · alerta automático de monitoramento.
        </div>
      </div></body></html>"""


def enviar_abertura(cfg, db_path, inc):
    """inc: dict de _Incidente.resumo() (unidade, afetados, nomes, primeira, ultima, tasy)."""
    unidade = inc['unidade']
    n = inc['afetados']
    tasy = inc['tasy']
    agora = datetime.now().strftime('%H:%M:%S')

    # Dois casos, por UNIDADE (os painéis são os únicos sensores no caminho de
    # rede daquela unidade):
    #  - tem sinal de erro do Tasy → provável queda do Tasy/firewall SÓ nesta
    #    unidade (o monitor de host, que fica na Unidade II, não enxerga isso).
    #  - sem sinal de Tasy → painéis reiniciando por outra causa (rede/energia
    #    local, etc.).
    if tasy:
        assunto = f"🚨 {unidade} — possível instabilidade no Tasy"
        titulo_txt = (f"Vários painéis da {unidade} começaram a apresentar erro de conexão com o "
                      f"Tasy quase ao mesmo tempo. Normalmente isso indica que o Tasy, ou a rede "
                      f"entre a {unidade} e o servidor, está instável agora. A outra unidade pode "
                      f"continuar funcionando normalmente.")
        cor, faixa = '#b02a37', f"🚨 {unidade} — possível instabilidade no Tasy"
        o_que_fazer = (f"O que fazer: verifique a conexão da {unidade} com o Tasy. "
                       f"Assim que os painéis voltarem ao normal, enviaremos um novo e-mail.")
    else:
        assunto = f"🚨 {unidade} — vários painéis reiniciando"
        titulo_txt = (f"Vários painéis da {unidade} reiniciaram sozinhos num curto intervalo. "
                      f"Não houve erro de conexão com o Tasy, então costuma ser algo local da "
                      f"unidade — como a rede ou a energia do local.")
        cor, faixa = '#b02a37', f"🚨 {unidade} — vários painéis reiniciando"
        o_que_fazer = (f"O que fazer: verifique a rede e a energia da {unidade}. "
                       f"Enviaremos um novo e-mail quando normalizar.")

    pares = [
        ('Unidade', unidade),
        ('Painéis afetados', n),
        ('Início', inc['primeira']),
        ('Último sinal', inc['ultima']),
    ]
    texto = _corpo_txt(titulo_txt, pares, paineis=_lista_afetados(inc['nomes']),
                       o_que_fazer=o_que_fazer)
    html = _card_html(cor, faixa, titulo_txt, pares, rodape=o_que_fazer)
    return _enviar_para_todos(cfg, db_path, assunto, texto, html)


# ── Alertas do host do Tasy (medição direta, independente de painéis) ────────

def enviar_tasy_down(cfg, db_path, dados):
    """Alerta autoritativo: o host do Tasy parou de responder."""
    host = dados.get('host', 'Tasy')
    quando = dados.get('detectado_em', datetime.now().strftime('%d/%m/%Y %H:%M:%S'))
    assunto = "🚨 Possível instabilidade no Tasy — todas as unidades"
    titulo_txt = ("O servidor do Tasy parou de responder. No momento, o Tasy aparenta estar "
                  "fora do ar para as duas unidades. Essa verificação é feita direto no servidor "
                  "do Tasy, então não depende dos painéis.")
    pares = [('Servidor', host), ('Detectado às', quando)]
    o_que_fazer = "Enviaremos um novo e-mail assim que o Tasy voltar a responder."
    texto = _corpo_txt(titulo_txt, pares, o_que_fazer=o_que_fazer)
    html = _card_html('#b02a37', "🚨 Possível instabilidade no Tasy — todas as unidades",
                      titulo_txt, pares, rodape=o_que_fazer)
    return _enviar_para_todos(cfg, db_path, assunto, texto, html)


def enviar_tasy_up(cfg, db_path, dados):
    """Recuperação: o host do Tasy voltou a responder."""
    host = dados.get('host', 'Tasy')
    quando = dados.get('restabelecido_em', datetime.now().strftime('%d/%m/%Y %H:%M:%S'))
    dur = dados.get('duracao_min')
    dur_txt = f"{dur} min" if dur else "—"
    assunto = "✅ Tasy normalizado — todas as unidades"
    titulo_txt = ("Boa notícia: o servidor do Tasy voltou a responder e o sistema aparenta estar "
                  "normal de novo nas duas unidades.")
    pares = [('Servidor', host), ('Voltou às', quando), ('Tempo fora do ar', dur_txt)]
    texto = _corpo_txt(titulo_txt, pares)
    html = _card_html('#0f7b6c', "✅ Tasy normalizado — todas as unidades", titulo_txt, pares)
    return _enviar_para_todos(cfg, db_path, assunto, texto, html)


def enviar_recuperacao(cfg, db_path, inc):
    unidade = inc['unidade']
    assunto = f"✅ {unidade} — situação normalizada"
    titulo_txt = (f"Os painéis da {unidade} voltaram a funcionar normalmente. O incidente "
                  f"anterior foi encerrado.")
    pares = [
        ('Unidade', unidade),
        ('Tempo do incidente', f"{inc.get('duracao_min', '?')} min"),
        ('Painéis afetados', inc['afetados']),
        ('Voltaram ao normal', inc.get('recuperados', inc['afetados'])),
    ]
    linhas_txt = _corpo_txt(titulo_txt, pares)
    html = _card_html('#0f7b6c', f"✅ {unidade} — situação normalizada", titulo_txt, pares)
    return _enviar_para_todos(cfg, db_path, assunto, linhas_txt, html)


def enviar_teste(cfg, db_path):
    """E-mail de teste para validar destinatários e SMTP a partir da página."""
    assunto = "Teste — alertas da Central de Operadores"
    texto = ("Este é um e-mail de teste dos alertas críticos da Central de Operadores.\n"
             "Se você recebeu, o envio está funcionando.")
    html = _card_html('#06534d', "✅ Teste de alerta", "Envio de alertas funcionando.",
                      [('Enviado em', datetime.now().strftime('%d/%m/%Y %H:%M:%S'))])
    return _enviar_para_todos(cfg, db_path, assunto, texto, html)
