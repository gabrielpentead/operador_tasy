#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Envio de e-mail por SMTP.

Usa apenas a biblioteca padrão (smtplib + email) — nenhuma dependência nova.

Regras que valem para todo este módulo:
  - Senha NUNCA vai para o log. Nem em erro, nem em depuração.
  - Falha de envio não derruba a aplicação: devolve (False, motivo) e quem
    chamou decide o que fazer.
  - Sem SMTP configurado, o envio é recusado de forma explícita, para o
    administrador perceber que precisa configurar em vez de achar que enviou.
"""

import ssl
import time
import smtplib
import logging
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid

logger = logging.getLogger("TasyServerCentral")


def smtp_configurado(cfg) -> bool:
    return bool(cfg.habilitado and cfg.servidor and cfg.remetente)


def enviar_email(cfg, destinatario: str, assunto: str, texto: str, html: str = None):
    """Envia um e-mail. Devolve (sucesso, mensagem_de_erro_ou_None).

    O corpo vai em texto puro e, opcionalmente, HTML — clientes que não
    renderizam HTML continuam legíveis.
    """
    if not smtp_configurado(cfg):
        return False, ('Envio de e-mail não configurado no servidor. '
                       'Defina a seção "email" em data/server_config.json.')

    if not destinatario:
        return False, 'Destinatário não informado'

    msg = EmailMessage()
    msg['Subject'] = assunto
    msg['From'] = formataddr((cfg.remetente_nome, cfg.remetente))
    msg['To'] = destinatario
    msg['Date'] = formatdate(localtime=True)
    msg.set_content(texto)
    if html:
        msg.add_alternative(html, subtype='html')

    try:
        if cfg.porta == 465:
            # 465 é SMTPS: TLS já na conexão, sem STARTTLS
            contexto = ssl.create_default_context()
            with smtplib.SMTP_SSL(cfg.servidor, cfg.porta,
                                  timeout=cfg.timeout, context=contexto) as s:
                if cfg.usuario:
                    s.login(cfg.usuario, cfg.senha)
                s.send_message(msg)
        else:
            with smtplib.SMTP(cfg.servidor, cfg.porta, timeout=cfg.timeout) as s:
                s.ehlo()
                if cfg.usar_tls:
                    s.starttls(context=ssl.create_default_context())
                    s.ehlo()
                # Servidor interno costuma aceitar sem autenticação
                if cfg.usuario:
                    s.login(cfg.usuario, cfg.senha)
                s.send_message(msg)

        logger.info(f"E-mail enviado para {destinatario}: {assunto}")
        return True, None

    except smtplib.SMTPAuthenticationError:
        logger.error("Falha de autenticação no SMTP (usuário ou senha do servidor de e-mail).")
        return False, 'Falha de autenticação no servidor de e-mail'
    except smtplib.SMTPRecipientsRefused:
        logger.warning(f"Servidor de e-mail recusou o destinatário {destinatario}")
        return False, 'Endereço de e-mail recusado pelo servidor'
    except (smtplib.SMTPException, OSError) as e:
        logger.error(f"Falha ao enviar e-mail para {destinatario}: {type(e).__name__}: {e}")
        return False, 'Não foi possível enviar o e-mail. Verifique a configuração de SMTP.'


# ── Mensagem de redefinição de senha ────────────────────────────────────────

def enviar_link_redefinicao(cfg, destinatario, nome, login, link, validade_min):
    """Envia o LINK de redefinição.

    A senha nunca viaja por e-mail: o link leva a uma tela onde a própria
    pessoa define a nova senha. Se a caixa postal for lida depois, o link já
    terá expirado ou sido consumido — ao contrário de uma senha, que
    continuaria válida ali para sempre.
    """
    assunto = 'Central de Operadores — redefinição de senha'

    texto = f"""Olá, {nome}.

Recebemos um pedido para redefinir a senha da sua conta na Central de
Operadores do Hospital São Vicente.

    Usuário: {login}

Abra o endereço abaixo para escolher uma nova senha:

{link}

Este link vale por {validade_min} minutos e só pode ser usado uma vez.

Se você não fez este pedido, ignore esta mensagem: sua senha atual continua
valendo e nada foi alterado.

--
NTI - Núcleo de Tecnologia da Informação
Esta é uma mensagem automática. Não responda.
"""

    html = f"""<!doctype html>
<html lang="pt-BR"><body style="margin:0;padding:24px;background:#f5f7f6;
  font-family:'Segoe UI',Roboto,Arial,sans-serif;color:#212529;">
  <div style="max-width:520px;margin:0 auto;background:#fff;border-radius:8px;
       overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.08);">
    <div style="background:#06534d;color:#fff;padding:20px 24px;">
      <div style="font-size:17px;font-weight:600;">Central de Operadores</div>
      <div style="font-size:13px;opacity:.85;">Hospital São Vicente</div>
    </div>
    <div style="padding:24px;">
      <p style="margin:0 0 16px;">Olá, <strong>{nome}</strong>.</p>
      <p style="margin:0 0 8px;">Recebemos um pedido para redefinir a senha da conta
        <strong style="font-family:Consolas,monospace;">{login}</strong>.</p>
      <p style="margin:0 0 22px;">Clique no botão abaixo para escolher uma nova senha:</p>

      <table role="presentation" style="margin:0 auto 22px;"><tr><td
        style="background:#06534d;border-radius:6px;">
        <a href="{link}" style="display:inline-block;padding:13px 28px;color:#fff;
           text-decoration:none;font-weight:600;font-size:15px;">Redefinir minha senha</a>
      </td></tr></table>

      <p style="margin:0 0 18px;font-size:12px;color:#586274;">
        Se o botão não funcionar, copie e cole este endereço no navegador:<br>
        <span style="word-break:break-all;color:#06534d;">{link}</span>
      </p>

      <p style="margin:0;padding:12px 14px;background:#fff8e6;border-left:3px solid #ff9800;
         font-size:13px;color:#664d03;">
        O link vale por <strong>{validade_min} minutos</strong> e só pode ser usado uma vez.
      </p>

      <p style="margin:16px 0 0;font-size:13px;color:#586274;">
        Se você não fez este pedido, ignore esta mensagem. Sua senha atual continua
        valendo e nada foi alterado.
      </p>
    </div>
    <div style="padding:14px 24px;background:#f5f7f6;font-size:11px;color:#8592a3;
         border-top:1px solid #dee2e6;">
      NTI — Núcleo de Tecnologia da Informação · mensagem automática, não responda.
    </div>
  </div>
</body></html>"""

    return enviar_email(cfg, destinatario, assunto, texto, html)


# ── Envio para vários destinatários (alertas) — BCC + retry ──────────────────

def enviar_email_multi(cfg, destinatarios, assunto, texto, html=None, tentativas=3):
    """Envia UMA mensagem para vários destinatários via BCC, com retry.

    Por que assim:
      - BCC: um único envelope entrega para todos — menos conexões, mais rápido,
        e um destinatário não vê o e-mail dos outros.
      - Retry com backoff: um alerta crítico não pode se perder por uma oscilação
        momentânea do SMTP. Falha permanente (auth/recusa) NÃO é repetida.

    Devolve (enviados, erro): enviados = nº de destinatários no envelope se saiu,
    0 se não saiu. Nunca levanta exceção.
    """
    if not smtp_configurado(cfg):
        return 0, ('Envio de e-mail não configurado no servidor.')
    destinos = [d for d in (destinatarios or []) if d]
    if not destinos:
        return 0, 'Sem destinatários'

    msg = EmailMessage()
    msg['Subject'] = assunto
    msg['From'] = formataddr((cfg.remetente_nome, cfg.remetente))
    # To é só cosmético (o próprio remetente); a entrega é feita pelo envelope
    # via to_addrs=destinos no send_message. Assim ninguém vê o e-mail do outro
    # e o remetente NÃO recebe cópia. O cabeçalho Bcc não é usado.
    msg['To'] = formataddr((cfg.remetente_nome, cfg.remetente))
    msg['Date'] = formatdate(localtime=True)
    try:
        msg['Message-ID'] = make_msgid(domain=cfg.remetente.split('@')[-1] or None)
    except Exception:
        pass
    msg.set_content(texto)
    if html:
        msg.add_alternative(html, subtype='html')

    ultimo_erro = None
    for tentativa in range(1, tentativas + 1):
        try:
            if cfg.porta == 465:
                contexto = ssl.create_default_context()
                with smtplib.SMTP_SSL(cfg.servidor, cfg.porta,
                                      timeout=cfg.timeout, context=contexto) as s:
                    if cfg.usuario:
                        s.login(cfg.usuario, cfg.senha)
                    s.send_message(msg, to_addrs=destinos)
            else:
                with smtplib.SMTP(cfg.servidor, cfg.porta, timeout=cfg.timeout) as s:
                    s.ehlo()
                    if cfg.usar_tls:
                        s.starttls(context=ssl.create_default_context())
                        s.ehlo()
                    if cfg.usuario:
                        s.login(cfg.usuario, cfg.senha)
                    s.send_message(msg, to_addrs=destinos)
            logger.info(f"Alerta enviado para {len(destinos)} destinatário(s): {assunto}")
            return len(destinos), None

        except smtplib.SMTPAuthenticationError:
            # Erro permanente: repetir não adianta.
            logger.error("Alerta NÃO enviado: falha de autenticação no SMTP.")
            return 0, 'Falha de autenticação no servidor de e-mail'
        except smtplib.SMTPRecipientsRefused:
            logger.error("Alerta NÃO enviado: servidor recusou os destinatários.")
            return 0, 'Destinatários recusados pelo servidor'
        except (smtplib.SMTPException, OSError) as e:
            ultimo_erro = f"{type(e).__name__}: {e}"
            if tentativa < tentativas:
                espera = 2 * tentativa      # 2s, 4s
                logger.warning(f"Envio de alerta falhou (tentativa {tentativa}/{tentativas}): "
                               f"{ultimo_erro}. Repetindo em {espera}s.")
                time.sleep(espera)
            else:
                logger.error(f"Alerta NÃO enviado após {tentativas} tentativas: {ultimo_erro}")

    return 0, ultimo_erro or 'Falha desconhecida no envio'
