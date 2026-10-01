#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sobe o servidor em modo de teste local, com um capturador de e-mail no lugar
do Gmail.

Serve para experimentar a redefinição de senha por link sem precisar de Senha
de app do Google e sem mandar e-mail de verdade para ninguém. As mensagens são
interceptadas aqui e o link aparece na tela.

NÃO altera data/server_config.json nem o banco: o SMTP é redirecionado por
variável de ambiente, que tem precedência sobre o arquivo. Ao encerrar, nada
fica para trás — a próxima partida normal volta a usar o Gmail configurado.

Uso:
    python testar_local.py

Encerre com Ctrl+C.
"""

import os
import re
import sys
import time
import email
import asyncio
import threading
import subprocess

PORTA_HTTP = 5000
PORTA_SMTP = 8025
CRLF = b"\r\n"
FIM_DADOS = b"\r\n.\r\n"

recebidos = []


class CapturaSMTP(asyncio.Protocol):
    """SMTP mínimo: aceita a mensagem, guarda o corpo e nunca entrega a ninguém.

    Acumula bytes e só recorta em linhas quando o buffer permite — os pedaços
    que chegam pelo TCP não respeitam limite de linha.
    """

    def connection_made(self, transporte):
        self.t = transporte
        self.buf = b""
        self.em_dados = False
        self.t.write(b"220 captura-local" + CRLF)

    def data_received(self, dados):
        self.buf += dados
        while True:
            if self.em_dados:
                fim = self.buf.find(FIM_DADOS)
                if fim == -1:
                    return
                recebidos.append(self.buf[:fim].decode("utf-8", "replace"))
                self.buf = self.buf[fim + len(FIM_DADOS):]
                self.em_dados = False
                self.t.write(b"250 ok" + CRLF)
                continue

            corte = self.buf.find(CRLF)
            if corte == -1:
                return
            linha, self.buf = self.buf[:corte], self.buf[corte + 2:]
            c = linha.upper()

            if c.startswith(b"EHLO") or c.startswith(b"HELO"):
                self.t.write(b"250-captura-local" + CRLF + b"250 OK" + CRLF)
            elif c.startswith(b"DATA"):
                self.em_dados = True
                self.t.write(b"354 envie" + CRLF)
            elif c.startswith(b"QUIT"):
                self.t.write(b"221 tchau" + CRLF)
                self.t.close()
                return
            else:
                self.t.write(b"250 OK" + CRLF)


def iniciar_captura():
    def rodar():
        laco = asyncio.new_event_loop()
        asyncio.set_event_loop(laco)
        laco.run_until_complete(laco.create_server(CapturaSMTP, "127.0.0.1", PORTA_SMTP))
        laco.run_forever()

    threading.Thread(target=rodar, daemon=True).start()
    time.sleep(0.8)


def texto_da_mensagem(bruta):
    msg = email.message_from_string(bruta)
    partes = [msg] if not msg.is_multipart() else list(msg.walk())
    for p in partes:
        if p.get_content_type() == 'text/plain':
            return msg, p.get_payload(decode=True).decode('utf-8', 'replace')
    return msg, ''


def vigiar_emails():
    vistos = 0
    while True:
        if len(recebidos) > vistos:
            for bruta in recebidos[vistos:]:
                msg, txt = texto_da_mensagem(bruta)
                link = re.search(r'(https?://\S+\?redefinir=[A-Za-z0-9_\-]+)', txt)
                print("\n" + "=" * 72)
                print(f"E-MAIL INTERCEPTADO  ->  {msg['To']}")
                print(f"assunto: {msg['Subject']}")
                if link:
                    print("\nabra este endereço no navegador:")
                    print(f"  {link.group(1)}")
                print("=" * 72 + "\n", flush=True)
            vistos = len(recebidos)
        time.sleep(0.4)


def main():
    aqui = os.path.dirname(os.path.abspath(__file__))
    os.chdir(aqui)

    iniciar_captura()

    # Redireciona o SMTP só para este processo filho. O arquivo de configuração
    # continua intocado, com o Gmail de verdade.
    ambiente = dict(
        os.environ,
        PYTHONIOENCODING='utf-8',
        TASY_SMTP_SERVIDOR='127.0.0.1',
        TASY_SMTP_PORTA=str(PORTA_SMTP),
        TASY_SMTP_TLS='false',
        TASY_SMTP_USUARIO='',      # capturador não pede autenticação
        TASY_SMTP_SENHA='',
    )

    print("=" * 72)
    print("  MODO DE TESTE LOCAL")
    print("=" * 72)
    print(f"  Painel ............. http://localhost:{PORTA_HTTP}")
    print(f"  E-mail ............. capturado em 127.0.0.1:{PORTA_SMTP} (não sai daqui)")
    print("  Configuração ....... intocada (data/server_config.json continua no Gmail)")
    print("  Banco .............. o de sempre, sem alteração")
    print()
    print("  Para testar: Esqueci minha senha -> o link aparece aqui embaixo.")
    print("  Ctrl+C para encerrar.")
    print("=" * 72, flush=True)

    threading.Thread(target=vigiar_emails, daemon=True).start()

    proc = subprocess.Popen(
        [sys.executable, 'run.py', '--host', '0.0.0.0', '--port', str(PORTA_HTTP)],
        cwd=aqui, env=ambiente)
    try:
        proc.wait()
    except KeyboardInterrupt:
        print("\nencerrando...")
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=10)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        print("servidor encerrado. Nada foi alterado na configuração.")


if __name__ == '__main__':
    main()
