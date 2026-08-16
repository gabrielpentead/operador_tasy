#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gerenciador do navegador Microsoft Edge para o Cliente Operador Tasy
Refatorado para ser uma fábrica de navegadores e suportar múltiplas instâncias.
"""

import os
import sys
import time
import subprocess
import logging
import tempfile
import shutil
import json
import requests
import zipfile
import ctypes
from ctypes import wintypes
from typing import Optional, Dict, Any

import psutil
from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options

from utils.constants import BROWSER_STARTUP_WAIT
from utils.system_utils import get_monitors_info
from core.config import OperadorConfig

logger = logging.getLogger("TasyOperador.BrowserManager")

class EdgeBrowserManager:
    """Fábrica de navegadores Edge. Lança e gerencia instâncias isoladas."""

    def __init__(self, config: Optional[OperadorConfig] = None):
        self.config = config or OperadorConfig()

    def _get_edge_version(self) -> Optional[str]:
        """Obtém a versão instalada do Microsoft Edge via registro do Windows."""
        try:
            cmd = ['reg', 'query', r'HKEY_CURRENT_USER\Software\Microsoft\Edge\BLBeacon', '/v', 'version']
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    if "version" in line:
                        version = line.split()[-1]
                        return version
            return None
        except Exception as e:
            logger.error(f"Erro ao ler versão do Edge: {e}")
            return None

    def _download_edgedriver(self, version: str, target_path: str) -> bool:
        """Baixa e extrai o EdgeDriver da versão específica."""
        urls = [
            f"https://msedgedriver.microsoft.com/{version}/edgedriver_win64.zip",
            f"https://msedgewebdriverstorage.blob.core.windows.net/edgewebdriver/{version}/edgedriver_win64.zip",
        ]

        zip_path = target_path.replace(".exe", ".zip")

        logger.info(f"🔄 Iniciando download do driver versão {version}...")
        print(f"   ⬇️  Baixando driver versão {version}...")

        for url in urls:
            try:
                response = requests.get(url, stream=True, timeout=10)

                if response.status_code == 200:
                    total_length = response.headers.get('content-length')

                    with open(zip_path, 'wb') as f:
                        if total_length is None:
                            f.write(response.content)
                        else:
                            dl = 0
                            total_length = int(total_length)
                            for data in response.iter_content(chunk_size=4096):
                                dl += len(data)
                                f.write(data)
                                done = int(50 * dl / total_length)
                                sys.stdout.write(f"\r   ⏳ Progresso: [{'=' * done}{' ' * (50 - done)}] {int(dl/total_length*100)}%")
                                sys.stdout.flush()

                    print()

                    print("   📦 Extraindo arquivos...")
                    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                        for file in zip_ref.namelist():
                            if file.endswith("msedgedriver.exe"):
                                source = zip_ref.open(file)
                                target = open(target_path, "wb")
                                with source, target:
                                    shutil.copyfileobj(source, target)
                                break

                    try: os.remove(zip_path)
                    except: pass

                    success_msg = f"✅ Driver atualizado com sucesso para versão {version}."
                    logger.info(success_msg)
                    print(f"   {success_msg}")
                    return True
            except Exception as e:
                logger.debug(f"Tentativa de download falhou para {url}: {e}")
                continue

        logger.error("❌ Falha ao baixar EdgeDriver de todas as fontes.")
        print("   ❌ Não foi possível baixar o driver automaticamente. Verifique sua conexão.")
        return False

    def _get_driver_actual_version(self, driver_path: str) -> Optional[str]:
        """Lê a versão real do msedgedriver.exe executando --version.

        Garante que o arquivo físico corresponde ao que o config.ini diz.
        Se o arquivo não existe ou falha, retorna None.
        """
        if not os.path.exists(driver_path):
            return None
        try:
            result = subprocess.run(
                [driver_path, "--version"],
                capture_output=True, text=True, timeout=5,
                creationflags=0x08000000 if os.name == 'nt' else 0,
            )
            # Saída: "MSEdgeDriver 149.0.4022.80 (...)"
            import re
            m = re.search(r'(\d+\.\d+\.\d+\.\d+)', result.stdout)
            if m:
                return m.group(1)
        except Exception:
            pass
        return None

    def _needs_driver_update(self, edge_version: str, driver_path: str) -> bool:
        """Retorna True se o driver precisar de atualização.

        Verifica tanto o config.ini quanto a versão real do executável,
        para proteger contra: Edge auto-update silencioso, download anterior
        que falhou, ou config.ini desatualizado.
        """
        if not os.path.exists(driver_path):
            return True

        # 1. Verificação rápida pelo config (major version)
        self.config.load_config()
        stored = self.config.get_system_config().get('edgedriver_version', '')
        edge_major = edge_version.split('.')[0]
        stored_major = stored.split('.')[0] if stored else ''
        if edge_major != stored_major:
            return True

        # 2. Verificação real: executar o driver e comparar major version
        actual = self._get_driver_actual_version(driver_path)
        if actual is None:
            return True
        actual_major = actual.split('.')[0]
        if edge_major != actual_major:
            logger.warning(
                f"⚠️ Config diz driver={stored}, mas executável reporta={actual}. "
                f"Edge={edge_version}. Atualizando driver."
            )
            return True

        return False

    def check_and_update_driver(self) -> str:
        """Verifica versão do Edge e atualiza o driver se necessário.

        Compara a versão real do executável msedgedriver (não só o config)
        com a major version do Edge instalado, garantindo que um auto-update
        silencioso do Edge não deixe o driver incompatível.
        """
        app_dir = (os.path.dirname(sys.executable) if getattr(sys, 'frozen', False)
                   else os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        local_driver_path = os.path.join(app_dir, "msedgedriver.exe")

        current_edge_version = self._get_edge_version()
        if not current_edge_version:
            logger.warning("⚠️ Não foi possível detectar a versão do Edge. Usando driver existente.")
            return local_driver_path

        if self._needs_driver_update(current_edge_version, local_driver_path):
            msg = f"🔄 Driver desatualizado — Edge={current_edge_version}. Baixando driver compatível..."
            logger.info(msg)
            print(f"   {msg}")

            # Encerra processos msedgedriver em uso antes de sobrescrever
            try:
                for proc in psutil.process_iter(['pid', 'name']):
                    if proc.info['name'] == 'msedgedriver.exe':
                        proc.kill()
            except Exception:
                pass

            if self._download_edgedriver(current_edge_version, local_driver_path):
                self.config.set_edgedriver_version(current_edge_version)
                logger.info(f"✅ Driver atualizado para Edge {current_edge_version}.")
            else:
                logger.error("❌ Falha no download do driver. A automação pode falhar.")
        else:
            logger.info(f"✅ Driver compatível com Edge {current_edge_version}.")

        return local_driver_path

    def _get_edge_executable_path(self) -> Optional[str]:
        for path in [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
        ]:
            if os.path.exists(path): return path
        logger.error("❌ Microsoft Edge não encontrado.")
        return None

    def _get_driver_path(self) -> str:
        app_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(app_dir, "msedgedriver.exe")

    # ── Controle da barra de tarefas ─────────────────────────────────────────

    def _set_taskbar_visible(self, visible: bool):
        """Mostra ou oculta a barra de tarefas do Windows.

        Chamado antes de iniciar o Edge (ocultar) e ao parar o navegador (mostrar),
        garantindo que a barra nunca apareça durante restarts por comando remoto,
        crash recovery ou reinicialização de máquina.

        Cobre o taskbar principal (Shell_TrayWnd) e os taskbars de monitores
        secundários (Shell_SecondaryTrayWnd), ambos encontrados por EnumWindows
        para não depender de um HWND estático.
        """
        if os.name != 'nt':
            return
        SW_HIDE = 0
        SW_SHOW = 5
        cmd = SW_SHOW if visible else SW_HIDE
        targets = ("Shell_TrayWnd", "Shell_SecondaryTrayWnd")
        try:
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            for cls in targets:
                hwnd = user32.FindWindowW(cls, None)
                if hwnd:
                    user32.ShowWindow(hwnd, cmd)
            action = "restaurada" if visible else "ocultada"
            logger.info(f"  - Barra de tarefas {action}.")
        except Exception as e:
            logger.debug(f"_set_taskbar_visible({visible}) falhou (não crítico): {e}")

    def _allow_foreground(self):
        """Remove o foreground lock do Windows e autoriza qualquer processo a trazer
        sua janela ao primeiro plano.

        Chamado sempre antes de lançar o Edge, independente de quem acionou o restart
        (boot, operador_agent, crash recovery ou comando remoto do servidor).

        Sem isso, quando operador.exe roda sem janela visível (console oculto pelo
        operador_agent) e o restart vem de um comando remoto, o foreground lock ainda
        está ativo — SetForegroundWindow é ignorado, o kiosk não reclama o foco e
        a barra de tarefas permanece visível.

        LockSetForegroundWindow(LSFW_UNLOCK=2): remove o lock explicitamente.
        AllowSetForegroundWindow(ASFW_ANY):     permite que qualquer processo filho
                                                chame SetForegroundWindow com sucesso.
        """
        if os.name != 'nt':
            return
        LSFW_UNLOCK = 2
        ASFW_ANY    = 0xFFFFFFFF
        try:
            ctypes.windll.user32.LockSetForegroundWindow(LSFW_UNLOCK)
        except Exception:
            pass
        try:
            ctypes.windll.user32.AllowSetForegroundWindow(ASFW_ANY)
        except Exception as e:
            logger.debug(f"AllowSetForegroundWindow falhou (não crítico): {e}")

    def _force_window_foreground(self, pid: int) -> bool:
        """Localiza a janela principal do Edge pelo PID e chama SetForegroundWindow."""
        if os.name != 'nt':
            return False
        try:
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            found = {"hwnd": None}

            def _enum(hwnd, _lparam):
                wpid = wintypes.DWORD(0)
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
                if wpid.value == pid and user32.IsWindowVisible(hwnd):
                    buf = ctypes.create_unicode_buffer(256)
                    user32.GetClassNameW(hwnd, buf, 256)
                    if buf.value in ("Chrome_WidgetWin_1", "Chrome_WidgetWin_0"):
                        found["hwnd"] = hwnd
                        return False
                return True

            user32.EnumWindows(WNDENUMPROC(_enum), 0)
            if found["hwnd"]:
                user32.SetForegroundWindow(found["hwnd"])
                logger.info(f"  - Janela kiosk do Edge (HWND={found['hwnd']}) definida como foreground.")
                return True
            return False
        except Exception as e:
            logger.debug(f"SetForegroundWindow no Edge falhou (não crítico): {e}")
            return False

    def _start_foreground_watcher(self, pid: int, duration_secs: int = 20):
        """Thread que tenta manter a janela kiosk do Edge em foreground durante os
        primeiros N segundos após o boot ou reinício.

        No boot do Windows, o Desktop Window Manager pode ainda estar inicializando
        quando o operador_agent dispara, fazendo com que SetForegroundWindow seja
        ignorado na primeira chamada. O watcher repete as tentativas a cada 2s durante
        `duration_secs` segundos para garantir que o kiosk consiga esconder a barra de
        tarefas independentemente do momento do boot.
        """
        if os.name != 'nt':
            return

        import threading

        def _watch():
            deadline = time.time() + duration_secs
            while time.time() < deadline:
                time.sleep(2)
                self._allow_foreground()
                if self._force_window_foreground(pid):
                    # Encontrou e enviou — reduz a frequência mas continua até o fim
                    # para resistir a eventuais flutuações de foco.
                    time.sleep(3)

        threading.Thread(target=_watch, daemon=True, name="ForegroundWatcher").start()
        logger.info(f"  - ForegroundWatcher iniciado para PID {pid} ({duration_secs}s).")

    def _cleanup_previous_session(self, debug_port: int):
        """Mata processos Edge residuais na porta e limpa diretórios de perfil."""
        # 1. Matar qualquer processo Edge ainda usando esta porta de debug
        #
        # O tratamento de erro é POR PROCESSO, de propósito. Com um try/except
        # envolvendo o laço inteiro, uma única exceção (AccessDenied ao matar,
        # falha ao ler cmdline, processo que morre durante a varredura) abortava
        # a varredura e os processos ainda não examinados nunca eram verificados.
        # Se um deles fosse justamente o que segurava a porta, o Edge não subia
        # e só um reset geral resolvia. Aqui, a falha em um processo não impede
        # o exame dos demais.
        examinados = 0
        mortos = 0
        try:
            proc_iter = psutil.process_iter(['pid', 'name', 'cmdline'])
        except Exception as e:
            proc_iter = []
            logger.error(f"Erro ao listar processos: {e}")

        for proc in proc_iter:
            try:
                if proc.info['name'] not in ('msedge.exe', 'Microsoft Edge'):
                    continue
                examinados += 1
                cmdline = ' '.join(proc.info.get('cmdline') or [])
                if f'--remote-debugging-port={debug_port}' not in cmdline:
                    continue
                logger.warning(f"🔫 Matando processo Edge residual na porta {debug_port} (PID {proc.info['pid']})...")
                p = psutil.Process(proc.info['pid'])
                for child in p.children(recursive=True):
                    try:
                        child.kill()
                    except Exception:
                        pass   # um filho que resista não pode impedir o kill do pai
                p.kill()
                mortos += 1
            except psutil.NoSuchProcess:
                continue
            except Exception as e:
                # Falhou neste processo: registra e SEGUE examinando os demais.
                logger.warning(f"   - Falha ao tratar processo Edge residual: {e}")
                continue

        logger.info(f"  - Varredura de resíduos na porta {debug_port}: "
                    f"{examinados} processo(s) Edge examinado(s), {mortos} encerrado(s).")

        time.sleep(2)

        # 2. Limpar diretórios de perfil temporários.
        #
        # A LISTAGEM é síncrona e a REMOÇÃO é assíncrona, de propósito:
        #
        #   - `os.listdir` é barato. O `shutil.rmtree` é que custa caro: um perfil
        #     do Edge tem milhares de arquivos e, com processos órfãos segurando
        #     handles, a remoção chegou a atrasar a subida do painel em dezenas de
        #     segundos numa máquina de hardware limitado. Tirar isso do caminho
        #     crítico é o objetivo.
        #
        #   - Apagar diretórios velhos NÃO é pré-requisito de nada: o mkdtemp()
        #     logo abaixo cria um diretório novo e único a cada lançamento.
        #
        #   - Fazer a listagem AQUI, antes de retornar, é o que torna isso seguro.
        #     A thread só apaga o que JÁ existia neste instante. O perfil novo é
        #     criado depois, não está na lista, e portanto nunca pode ser apagado
        #     por engano — o que derrubaria o navegador recém-iniciado.
        antigos = []
        try:
            temp_dir = tempfile.gettempdir()
            prefix = f"tasy_edge_{debug_port}_"
            antigos = [os.path.join(temp_dir, nome)
                       for nome in os.listdir(temp_dir)
                       if nome.startswith(prefix)]
        except Exception as e:
            logger.error(f"❌ Erro ao listar sessões anteriores: {e}")

        if antigos:
            import threading

            logger.info(f"🧹 {len(antigos)} diretório(s) de sessão anterior na porta "
                        f"{debug_port}: removendo em segundo plano (não bloqueia a subida).")

            def _remover(caminhos):
                removidos = 0
                for caminho in caminhos:
                    try:
                        shutil.rmtree(caminho, ignore_errors=True)
                        if not os.path.exists(caminho):
                            removidos += 1
                    except Exception:
                        pass   # lixo que resiste fica para a próxima execução
                logger.info(f"🧹 Limpeza em segundo plano concluída na porta {debug_port}: "
                            f"{removidos}/{len(caminhos)} diretório(s) removido(s).")

            threading.Thread(target=_remover, args=(antigos,), daemon=True,
                             name=f"LimpezaPerfis-{debug_port}").start()

    def _seed_profile_preferences(self, user_data_dir: str):
        """Grava preferências do Edge no perfil recém-criado, ANTES de lançar o navegador.

        Por que escrever o arquivo em vez de usar o Selenium: o Edge é iniciado por
        subprocess.Popen e o Selenium apenas se ANEXA a ele via debuggerAddress.
        Nesse modelo, options.add_experimental_option("prefs", ...) é silenciosamente
        ignorado — só funciona quando é o driver que lança o navegador.

        Por que semear em vez de confiar no clique do usuário: o perfil é temporário
        (mkdtemp) e removido em stop_browser(), então qualquer preferência marcada na
        tela se perde na próxima inicialização. Semeando aqui, a preferência vale
        desde a PRIMEIRA execução e em todas as seguintes, sem depender de ninguém
        clicar em nada.

        Escopo: apenas avisos do próprio Edge que se sobrepõem ao painel. Não altera
        idioma, vozes, permissões, rede, cookies, sessão nem qualquer comportamento
        do Tasy.
        """
        try:
            default_dir = os.path.join(user_data_dir, "Default")
            os.makedirs(default_dir, exist_ok=True)

            prefs = {
                # Remove a barra "Traduzir esta página?". O painel do Tasy é servido
                # com <html lang="en">, então o Edge oferece tradução a cada start.
                "translate": {"enabled": False},
                # Remove o balão "Salvar senha?", disparado pelo login automático
                # da automação num perfil que nasce zerado toda vez.
                "credentials_enable_service": False,
                "profile": {"password_manager_enabled": False},
            }

            with open(os.path.join(default_dir, "Preferences"), "w", encoding="utf-8") as f:
                json.dump(prefs, f)

            logger.info("  - Preferências do perfil semeadas (tradução e salvar-senha desativados).")
        except Exception as e:
            # Falha aqui é puramente cosmética: o Edge sobe normalmente, apenas
            # volta a exibir os avisos. Nunca pode impedir o painel de iniciar.
            logger.warning(f"  - Não foi possível semear preferências do perfil (não crítico): {e}")

    def start_browser(self, debug_port: int, monitor_index: Optional[int] = None) -> Optional[Dict[str, Any]]:
        logger.info(f"🚀 Lançando nova instância do Edge (Porta: {debug_port}, Monitor: {monitor_index if monitor_index is not None else 'padrão'})...")

        self._cleanup_previous_session(debug_port)

        # Oculta a barra de tarefas antes de lançar o Edge em modo kiosk.
        # Garante que ela nunca apareça mesmo durante restarts por comando remoto.
        self._set_taskbar_visible(False)

        edge_path = self._get_edge_executable_path()
        if not edge_path:
            self._set_taskbar_visible(True)   # restaura se Edge não for encontrado
            return None

        user_data_dir = tempfile.mkdtemp(prefix=f"tasy_edge_{debug_port}_")
        self._seed_profile_preferences(user_data_dir)

        cmd = [
            edge_path, f"--remote-debugging-port={debug_port}",
            f"--user-data-dir={user_data_dir}",
            "--no-first-run",
            "--disable-sync",
            "--no-default-browser-check",
            "--disable-session-crashed-bubble",
            "--disable-popup-blocking"
        ]

        try:
            monitors = get_monitors_info()
            if monitor_index is not None and monitor_index < len(monitors):
                monitor = monitors[monitor_index]
                logger.info(f"  - Posicionando janela no monitor {monitor_index}: {monitor['width']}x{monitor['height']} em ({monitor['x']}, {monitor['y']})")
                cmd.append(f"--window-position={monitor['x']},{monitor['y']}")
                cmd.append("--kiosk")
            else:
                cmd.append("--start-maximized")
        except Exception as e:
            logger.error(f"Falha ao obter informações de monitor, iniciando maximizado: {e}")
            cmd.append("--start-maximized")

        edge_process = None
        try:
            creation_flags = 0x08000000 if os.name == 'nt' else 0
            # Autoriza o processo filho (Edge) a trazer sua janela ao primeiro plano.
            # Necessário quando operador.exe roda sem janela visível (console oculto
            # pelo operador_agent), pois nesse caso o Windows bloquearia SetForegroundWindow.
            self._allow_foreground()
            edge_process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creation_flags)
            logger.info(f"  - Processo Edge iniciado com PID: {edge_process.pid}")

            time.sleep(BROWSER_STARTUP_WAIT)

            service = Service(self._get_driver_path())
            options = Options()
            options.use_chromium = True
            options.add_experimental_option("debuggerAddress", f"localhost:{debug_port}")

            logger.info(f"  - Conectando Selenium ao Edge na porta {debug_port}...")

            # Retry — renderer pode ainda estar subindo
            driver = None
            last_error = None
            for attempt in range(1, 4):
                try:
                    driver = webdriver.Edge(service=service, options=options)
                    break
                except Exception as e:
                    last_error = e
                    err_msg = str(e)

                    # Detecta incompatibilidade de versão Edge ↔ driver e faz update automático
                    if 'version' in err_msg.lower() and attempt == 1:
                        logger.warning(
                            f"  - Detectada incompatibilidade de versão Edge/driver. "
                            f"Acionando atualização automática do msedgedriver..."
                        )
                        try:
                            edge_ver = self._get_edge_version()
                            driver_path = self._get_driver_path()
                            if edge_ver and self._download_edgedriver(edge_ver, driver_path):
                                self.config.set_edgedriver_version(edge_ver)
                                logger.info(f"  - Driver atualizado para {edge_ver}. Reconectando Selenium...")
                                service = Service(driver_path)   # recria o Service com driver novo
                        except Exception as upd_err:
                            logger.error(f"  - Falha no update emergencial do driver: {upd_err}")

                    if attempt < 3:
                        logger.warning(f"  - Tentativa {attempt}/3 falhou. Aguardando 3s...")
                        time.sleep(3)

            if driver is None:
                raise last_error

            driver.implicitly_wait(10)
            logger.info(f"✅ Navegador conectado e pronto na porta {debug_port}.")

            # Força foreground imediato e inicia watcher para os primeiros 20s.
            # O watcher é essencial no boot do Windows: o DWM pode ainda não ter
            # terminado de carregar quando o operador_agent dispara, então a primeira
            # chamada a SetForegroundWindow pode ser silenciosamente ignorada.
            self._force_window_foreground(edge_process.pid)
            self._start_foreground_watcher(edge_process.pid, duration_secs=20)

            return {"driver": driver, "process": edge_process, "user_data_dir": user_data_dir}

        except Exception as e:
            logger.error(f"❌ Erro crítico ao iniciar navegador na porta {debug_port}: {e}", exc_info=True)
            # Restaura a barra de tarefas: se o browser não subiu, o operador
            # precisa da barra visível para diagnóstico ou intervenção manual.
            self._set_taskbar_visible(True)
            # Matar processo Edge órfão para não acumular processos em memória
            if edge_process is not None:
                logger.warning(f"   - Encerrando processo Edge órfão (PID {edge_process.pid})...")
                try:
                    p = psutil.Process(edge_process.pid)
                    for child in p.children(recursive=True):
                        child.kill()
                    p.kill()
                except Exception:
                    try: edge_process.kill()
                    except Exception: pass
            if user_data_dir and os.path.exists(user_data_dir):
                shutil.rmtree(user_data_dir, ignore_errors=True)
            return None

    def stop_browser(self, browser_instance: Dict[str, Any]):
        if not browser_instance: return

        process = browser_instance.get("process")
        driver = browser_instance.get("driver")
        user_data_dir = browser_instance.get("user_data_dir")
        pid = process.pid if process else 'N/A'

        logger.info(f"⏹️ Fechando instância do navegador (PID: {pid})...")

        # Etapa 1: Fechar graciosamente via Selenium
        if driver:
            try:
                driver.quit()
                logger.info(f"   - Comando driver.quit() enviado.")
            except Exception as e:
                logger.warning(f"   - ⚠️ Erro durante driver.quit() (pode já estar fechado): {e}")

        # Etapa 2: Finalizar processo principal e sua árvore
        if pid != 'N/A':
            try:
                parent = psutil.Process(pid)
                logger.info(f"   - Encerrando árvore de processos do PID {pid}...")
                for child in parent.children(recursive=True):
                    try: child.terminate()
                    except psutil.NoSuchProcess: pass
                parent.terminate()
                _, alive = psutil.wait_procs([parent], timeout=3)
                if alive:
                    logger.warning(f"   - ⚠️ Processo PID {pid} não encerrou com terminate. Forçando com kill...")
                    parent.kill()
                logger.info(f"   - Árvore de processos do PID {pid} finalizada.")
            except psutil.NoSuchProcess:
                logger.info(f"   - Processo principal (PID {pid}) não encontrado. Provavelmente já havia sido encerrado.")
            except Exception as e:
                logger.error(f"   - ❌ Erro ao tentar terminar a árvore de processos do Edge (PID: {pid}): {e}")

        # Etapa 3: Caçar processos órfãos ainda usando o perfil
        if user_data_dir:
            killed_orphans = 0
            try:
                for p in psutil.process_iter(['pid', 'name', 'cmdline']):
                    if p.info['name'] == 'msedge.exe' and user_data_dir in " ".join(p.info['cmdline'] or []):
                        logger.warning(f"   - 🔫 Encontrado processo órfão (PID {p.info['pid']}) usando o perfil. Finalizando...")
                        p.kill()
                        killed_orphans += 1
                if killed_orphans > 0:
                    logger.info(f"   - ✅ {killed_orphans} processo(s) órfão(s) finalizado(s).")
            except Exception as e:
                logger.error(f"   - ❌ Erro durante a verificação de processos órfãos: {e}")

        # Etapa 4: Limpar diretório de perfil
        if user_data_dir and os.path.exists(user_data_dir):
            for i in range(3):
                try:
                    shutil.rmtree(user_data_dir)
                    logger.info(f"   - Diretório temporário {user_data_dir} removido com sucesso.")
                    break
                except OSError as e:
                    logger.error(f"   - ❌ Tentativa {i + 1}/3 de remover diretório {user_data_dir} falhou: {e}")
                    if i < 2:
                        time.sleep(2)
            else:
                logger.critical(f"   - 🚨 Não foi possível remover o diretório de perfil {user_data_dir} após 3 tentativas.")

        # Restaura a barra de tarefas ao parar o navegador.
        # O próximo start_browser() vai ocultá-la novamente quando o painel subir.
        self._set_taskbar_visible(True)
        logger.info(f"✅ Limpeza da instância do navegador (PID original: {pid}) concluída.")