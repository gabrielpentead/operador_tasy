#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================================================
 OPERADOR AGENT
============================================================================
 Wrapper de execucao para o "operador.exe" (TUI Textual em console).

 NAO altera nada da logica nem da interface do operador. Ele apenas:
   - Sobe o operador.exe OCULTO junto com o Windows (sem flash de console).
   - Mantem um icone na bandeja do sistema (System Tray).
   - Mostra / esconde a MESMA janela do console pelo menu da bandeja
     ou por duplo-clique no icone.
   - Minimizar a janela do console => esconde para a bandeja (instantaneo).
   - Desabilita o "X" do console pra ninguem MATAR o operador por engano.
     (Fechar de verdade = menu da bandeja > Sair.)

 Por que conhost? Em Windows 11 com Windows Terminal como terminal padrao,
 a janela visivel e do WT (ConPTY) e o GetConsoleWindow() aponta pra uma
 pseudo-janela invisivel; ShowWindow nela nao funciona. Forcando o
 conhost classico, a janela do console e a janela real e o hide/show
 funciona de forma confiavel.

 Deploy: coloque o operador_tray.exe (build com --noconsole) NA MESMA PASTA
 do operador.exe e aponte o atalho da pasta Inicializar para ele.

 Autor do wrapper: (gerado para o NTI - Hospital Sao Vicente)
============================================================================
"""

import os
import sys
import time
import socket
import threading
import subprocess
import configparser
from datetime import datetime
from urllib.parse import urlparse
import ctypes
from ctypes import wintypes

# ---------------------------------------------------------------------------
# Dependencias de terceiros (instalar: pip install pystray Pillow)
# ---------------------------------------------------------------------------
import pystray
from PIL import Image, ImageDraw

# ===========================================================================
# CONFIGURACAO
# ===========================================================================
# Nome do executavel REAL do operador (o seu console/TUI do TCC), na MESMA pasta.
# ATENCAO: este wrapper NUNCA pode ter o mesmo nome do alvo abaixo, senao ele
# lanca a si mesmo em LOOP INFINITO. Por isso o real fica 'operador.exe' e o
# wrapper fica 'operador_tray.exe' (nomes diferentes).
OPERADOR_EXE_NAME = "operador.exe"
APP_ICON_NAME     = "app.ico"        # icone usado na bandeja (mesma pasta / embutido)
APP_NAME          = "Operador Agent"
APP_TITLE         = "Operador Agent - Continuidade Operacional de Paineis"

# Forca o console classico (conhost). MANTENHA True.
# Motivo duplo:
#  (1) Em Win10/11 com Windows Terminal padrao, a janela visivel e do WT
#      (ConPTY) e o ShowWindow nao a controla.
#  (2) Em app de console normal, a janela pertence ao conhost.exe (outro PID),
#      entao localizar a janela pelo PID do operador.exe NAO funciona. Subindo
#      o conhost nos mesmos, o PID que recebemos JA e o dono da janela.
# Com False, o show/hide provavelmente NAO vai achar a janela. So use se souber
# o que esta fazendo.
FORCE_CONHOST = True

# Reiniciar automaticamente o operador caso o PROCESSO inteiro caia?
# (O operador ja tem auto-recuperacao interna; isto e so um watchdog do
#  processo. Deixe False para reinicio apenas manual.)
WATCHDOG_AUTORESTART = False

# Maquina ainda NAO registrada (sem credenciais salvas no config.ini)?
# True  => sobe o console VISIVEL para o usuario fazer o registro (como antes),
#          e o supervisor encerra (sem bandeja). No proximo boot, ja com
#          credenciais salvas, ele sobe oculto na bandeja normalmente.
# False => sobe sempre oculto (NAO recomendado: numa maquina sem registro o
#          input() ficaria travado num console invisivel).
VISIBLE_IF_UNREGISTERED = True

# Intervalos
FIND_WINDOW_TIMEOUT = 12.0   # segundos esperando a janela do console aparecer
MONITOR_INTERVAL    = 0.4    # segundos do loop de monitoramento

# ===========================================================================
# WINAPI (ctypes) - assinaturas com tipos corretos (evita truncamento em x64)
# ===========================================================================
user32   = ctypes.WinDLL("user32",   use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

# Constantes
SW_HIDE        = 0
SW_SHOWNORMAL  = 1
SW_SHOW        = 5
SW_RESTORE     = 9

SWP_NOSIZE     = 0x0001
SWP_NOMOVE     = 0x0002
SWP_NOZORDER   = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020

MF_BYCOMMAND   = 0x0000
SC_CLOSE       = 0xF060

EVENT_SYSTEM_MINIMIZESTART = 0x0016
WINEVENT_OUTOFCONTEXT      = 0x0000
WINEVENT_SKIPOWNPROCESS    = 0x0002

MB_OK            = 0x0
MB_ICONINFO      = 0x40
MB_ICONERROR     = 0x10
MB_TOPMOST       = 0x40000
MB_SETFOREGROUND = 0x10000

ERROR_ALREADY_EXISTS = 183

WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
WINEVENTPROC = ctypes.WINFUNCTYPE(
    None, wintypes.HANDLE, wintypes.DWORD, wintypes.HWND,
    wintypes.LONG, wintypes.LONG, wintypes.DWORD, wintypes.DWORD
)

# Prototipos
user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
user32.EnumWindows.restype  = wintypes.BOOL

user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype  = wintypes.DWORD

user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetClassNameW.restype  = ctypes.c_int

user32.IsWindow.argtypes  = [wintypes.HWND]
user32.IsWindow.restype   = wintypes.BOOL

user32.IsIconic.argtypes  = [wintypes.HWND]
user32.IsIconic.restype   = wintypes.BOOL

user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype  = wintypes.BOOL

user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype  = wintypes.BOOL

user32.GetSystemMenu.argtypes = [wintypes.HWND, wintypes.BOOL]
user32.GetSystemMenu.restype  = wintypes.HMENU

user32.DeleteMenu.argtypes = [wintypes.HMENU, wintypes.UINT, wintypes.UINT]
user32.DeleteMenu.restype  = wintypes.BOOL

user32.DrawMenuBar.argtypes = [wintypes.HWND]
user32.DrawMenuBar.restype  = wintypes.BOOL

user32.SetWinEventHook.argtypes = [
    wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE, WINEVENTPROC,
    wintypes.DWORD, wintypes.DWORD, wintypes.DWORD
]
user32.SetWinEventHook.restype = wintypes.HANDLE

user32.UnhookWinEvent.argtypes = [wintypes.HANDLE]
user32.UnhookWinEvent.restype  = wintypes.BOOL

user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
user32.GetMessageW.restype  = wintypes.BOOL

user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]

user32.MessageBoxW.argtypes = [wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.UINT]
user32.MessageBoxW.restype  = ctypes.c_int

kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
kernel32.CreateMutexW.restype  = wintypes.HANDLE

user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype  = wintypes.BOOL

user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype  = ctypes.c_int

user32.AllowSetForegroundWindow.argtypes = [wintypes.DWORD]
user32.AllowSetForegroundWindow.restype  = wintypes.BOOL

user32.LockSetForegroundWindow.argtypes = [wintypes.UINT]
user32.LockSetForegroundWindow.restype  = wintypes.BOOL

# --- Toolhelp32 para varrer a arvore de processos (sem psutil) ---
TH32CS_SNAPPROCESS = 0x00000002

class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", ctypes.c_char * 260),
    ]

kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
kernel32.CreateToolhelp32Snapshot.restype  = wintypes.HANDLE
kernel32.Process32First.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32)]
kernel32.Process32First.restype  = wintypes.BOOL
kernel32.Process32Next.argtypes  = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32)]
kernel32.Process32Next.restype   = wintypes.BOOL
kernel32.CloseHandle.argtypes    = [wintypes.HANDLE]
kernel32.CloseHandle.restype     = wintypes.BOOL


# ===========================================================================
# ESTADO GLOBAL
# ===========================================================================
class State:
    def __init__(self):
        self.proc = None                 # subprocess.Popen (conhost/operador)
        self.console_hwnd = None         # HWND da janela do console
        self.close_disabled = False      # ja desabilitamos o botao X?
        self.stopping = False            # encerramento em andamento
        self.restarting = False          # reinicio em andamento (nao acusar como "caiu")
        self.launched_at = None          # quando o operador (gerenciado) subiu
        self.lock = threading.Lock()

S = State()


# ===========================================================================
# HELPERS DE CAMINHO
# ===========================================================================
def base_dir():
    """Pasta onde o supervisor esta rodando (ao lado do operador.exe)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def resource_path(name):
    """Procura um recurso embutido (PyInstaller) ou ao lado do exe."""
    candidates = []
    if hasattr(sys, "_MEIPASS"):
        candidates.append(os.path.join(sys._MEIPASS, name))
    candidates.append(os.path.join(base_dir(), name))
    for c in candidates:
        if os.path.exists(c):
            return c
    return None

def operador_exe_path():
    return os.path.join(base_dir(), OPERADOR_EXE_NAME)

def conhost_path():
    root = os.environ.get("SystemRoot", r"C:\Windows")
    return os.path.join(root, "System32", "conhost.exe")


# ===========================================================================
# LOG DE DIAGNOSTICO (operador_agent.log ao lado do exe)
# ===========================================================================
def log_path():
    """operador_agent.log dentro da pasta 'logs' (junto do operador.log)."""
    d = os.path.join(base_dir(), "logs")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        d = base_dir()  # fallback se nao der pra criar a pasta
    return os.path.join(d, "operador_agent.log")

LOG_MAX_BYTES  = 2 * 1024 * 1024   # teto: 2 MB
LOG_KEEP_BYTES = 1 * 1024 * 1024   # ao cortar, preserva ~1 MB final (mais recente)

def _rotate_log_if_needed(path):
    """Mantem o arquivo unico abaixo de ~2 MB, descartando o inicio (antigo)
    e preservando o final (recente). Roda so quando passa do teto."""
    try:
        if not os.path.exists(path) or os.path.getsize(path) <= LOG_MAX_BYTES:
            return
        with open(path, "rb") as f:
            f.seek(-LOG_KEEP_BYTES, os.SEEK_END)
            tail = f.read()
        nl = tail.find(b"\n")          # alinha no inicio de uma linha
        if nl != -1:
            tail = tail[nl + 1:]
        with open(path, "wb") as f:
            f.write(b"---- log truncado (rotacao 2MB) ----\n")
            f.write(tail)
    except Exception:
        pass

def log(msg):
    """Grava uma linha com timestamp no operador_agent.log (best-effort)."""
    try:
        p = log_path()
        _rotate_log_if_needed(p)
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(p, "a", encoding="utf-8") as f:
            f.write(f"{ts} | {msg}\n")
    except Exception:
        pass


# ===========================================================================
# MESSAGEBOX (em thread, pra nao travar o loop da bandeja)
# ===========================================================================
def msgbox(text, title=APP_NAME, icon=MB_ICONINFO):
    def _show():
        user32.MessageBoxW(None, text, title, MB_OK | icon | MB_TOPMOST | MB_SETFOREGROUND)
    threading.Thread(target=_show, daemon=True).start()


# ===========================================================================
# FOREGROUND UNLOCK
# ===========================================================================
def unlock_foreground():
    """Remove restricoes de SetForegroundWindow para que processos filhos
    (Edge em kiosk) possam trazer suas janelas ao primeiro plano sem bloqueio.

    No boot do Windows, o foreground lock pode estar ativo antes do Desktop
    terminar de carregar. Chamar LockSetForegroundWindow(LSFW_UNLOCK) libera
    essa restricao, e AllowSetForegroundWindow(ASFW_ANY) permite que qualquer
    processo subsequente reivindique o foreground — necessario para que o kiosk
    esconda a barra de tarefas corretamente.
    """
    LSFW_UNLOCK = 2
    ASFW_ANY    = 0xFFFFFFFF
    try:
        user32.LockSetForegroundWindow(LSFW_UNLOCK)
    except Exception:
        pass
    try:
        user32.AllowSetForegroundWindow(ASFW_ANY)
    except Exception:
        pass


# ===========================================================================
# LANCAR / ENCERRAR O OPERADOR
# ===========================================================================
def ensure_conhost_default():
    """Forca o Windows Console Host (conhost) como terminal padrao do usuario,
    desabilitando o handoff para o Windows Terminal.

    Por que: com o Windows Terminal como padrao, o console do operador roda via
    ConPTY e o GetConsoleWindow()/janela visivel viram uma janela do WT (ou uma
    pseudo-janela invisivel), e o ShowWindow nao consegue mostrar/esconder a
    janela certa -> o 'Abrir console' falha. Forcando o conhost, a janela do
    console e uma ConsoleWindowClass real, localizavel e controlavel.

    HKCU\\Console\\%%Startup (literal, com %% mesmo). Nao precisa admin.
    Reaplicado a cada boot porque o Windows Terminal as vezes reseta o valor.
    GUID do conhost confirmado na doc da Microsoft:
    {B23D10C0-E52E-411E-9D5B-C09FDF709C7D}
    """
    CONHOST = "{B23D10C0-E52E-411E-9D5B-C09FDF709C7D}"
    try:
        import winreg
        key = winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER, r"Console\%%Startup", 0,
            winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE
        )
        winreg.SetValueEx(key, "DelegationConsole", 0, winreg.REG_SZ, CONHOST)
        winreg.SetValueEx(key, "DelegationTerminal", 0, winreg.REG_SZ, CONHOST)
        # readback para confirmar
        dc, _ = winreg.QueryValueEx(key, "DelegationConsole")
        dt, _ = winreg.QueryValueEx(key, "DelegationTerminal")
        winreg.CloseKey(key)
        ok = (dc == CONHOST and dt == CONHOST)
        log(f"[conhost] registro gravado. DelegationConsole={dc} DelegationTerminal={dt} ok={ok}")
        return ok
    except Exception as e:
        log(f"[conhost] FALHA ao gravar registro: {e!r}")
        return False


def _build_startupinfo_hidden():
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = SW_HIDE     # console nasce escondido
    return si

def launch_operador():
    """Sobe o operador.exe em um console proprio, ja oculto."""
    exe = operador_exe_path()
    if not os.path.exists(exe):
        msgbox(f"Nao encontrei:\n{exe}\n\nColoque o operador_tray ao lado do {OPERADOR_EXE_NAME}.",
               "Operador Agent - erro", MB_ICONERROR)
        return None

    si = _build_startupinfo_hidden()
    CREATE_NEW_CONSOLE = 0x00000010

    if FORCE_CONHOST and os.path.exists(conhost_path()):
        # conhost.exe hospeda o operador num console classico (hide/show confiavel)
        cmd = [conhost_path(), exe]
        creationflags = 0  # o proprio conhost cria o console
    else:
        cmd = [exe]
        creationflags = CREATE_NEW_CONSOLE

    proc = subprocess.Popen(
        cmd,
        cwd=base_dir(),
        startupinfo=si,
        creationflags=creationflags,
        close_fds=True,
    )
    log(f"[launch] cmd={cmd} -> pid={proc.pid} (FORCE_CONHOST={FORCE_CONHOST})")
    return proc

def kill_tree(pid):
    """Mata o processo e toda a arvore (operador + Edge + msedgedriver)."""
    try:
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            creationflags=0x08000000,  # CREATE_NO_WINDOW
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


def operador_is_ready():
    """Decide se o operador vai subir CALADO (sem input()) e, portanto, se e
    seguro roda-lo oculto.

    Replica has_any_credentials() do operador SEM importar o codigo dele,
    lendo o config.ini diretamente:
      - True  => existe credencial salva => sobe calado => pode ficar oculto.
      - False => vai pedir registro interativo (input()) => precisa visivel.

    IMPORTANTE: a chave do usuario no ini e 'usuario' (NAO 'username'); ter
    apenas 'id' preenchido NAO garante start calado (se faltar credencial e o
    servidor estiver fora, ele cai no registro offline interativo).
    """
    path = os.path.join(base_dir(), "config.ini")
    if not os.path.exists(path):
        return False  # sem arquivo => maquina nova => registrar
    try:
        cp = configparser.ConfigParser()
        cp.read(path, encoding="utf-8")

        def usuario(section):
            if not cp.has_section(section):
                return ""
            return (cp.get(section, "usuario", fallback="") or "").strip()

        separadas = cp.getboolean("operador", "usa_credenciais_separadas", fallback=False)
        if separadas:
            return bool(usuario("tasy_monitor") and usuario("tasy_totem"))
        return bool(usuario("tasy_compartilhado"))
    except Exception:
        # Em duvida, mostra visivel: e mais seguro que travar oculto no input().
        return False


def launch_operador_visible():
    """Sobe o operador.exe com console VISIVEL (para o registro interativo).
    Comportamento equivalente ao atalho antigo apontando direto pro exe."""
    exe = operador_exe_path()
    if not os.path.exists(exe):
        msgbox(f"Nao encontrei:\n{exe}\n\nColoque o operador_tray ao lado do {OPERADOR_EXE_NAME}.",
               "Operador Agent - erro", MB_ICONERROR)
        return None
    CREATE_NEW_CONSOLE = 0x00000010
    try:
        return subprocess.Popen(
            [exe], cwd=base_dir(),
            creationflags=CREATE_NEW_CONSOLE,  # console visivel proprio (stdin OK)
            close_fds=True,
        )
    except Exception:
        return None


# ===========================================================================
# LOCALIZAR A JANELA DO CONSOLE
# Estrategia robusta: junta o PID lancado + TODOS os descendentes e aceita a
# janela "ConsoleWindowClass" pertencente a qualquer um deles. Se nao achar,
# loga um dump de janelas relevantes para diagnostico.
# ===========================================================================
def _get_class_name(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value

def _get_window_text(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(hwnd, buf, 256)
    return buf.value

def snapshot_processes():
    """dict: pid -> (ppid, exename)."""
    procs = {}
    hSnap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not hSnap or hSnap == wintypes.HANDLE(-1).value:
        return procs
    try:
        entry = PROCESSENTRY32()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32)
        ok = kernel32.Process32First(hSnap, ctypes.byref(entry))
        while ok:
            try:
                name = entry.szExeFile.decode("latin-1", "replace")
            except Exception:
                name = "?"
            procs[int(entry.th32ProcessID)] = (int(entry.th32ParentProcessID), name)
            ok = kernel32.Process32Next(hSnap, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(hSnap)
    return procs

def descendant_pids(root_pid):
    """Conjunto com o root_pid + todos os descendentes (filhos, netos...)."""
    procs = snapshot_processes()
    children = {}
    for pid, (ppid, _name) in procs.items():
        children.setdefault(ppid, []).append(pid)
    result = {root_pid}
    stack = [root_pid]
    while stack:
        p = stack.pop()
        for c in children.get(p, []):
            if c not in result:
                result.add(c)
                stack.append(c)
    return result, procs

def _find_console_in_pids(pids):
    found = {"hwnd": None}
    def _enum(hwnd, lparam):
        wpid = wintypes.DWORD(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
        if wpid.value in pids and _get_class_name(hwnd) == "ConsoleWindowClass":
            found["hwnd"] = hwnd
            return False
        return True
    user32.EnumWindows(WNDENUMPROC(_enum), 0)
    return found["hwnd"]

def dump_windows(target_pids):
    """Loga janelas relevantes (da arvore + qualquer console/WT/pseudo)."""
    procs = snapshot_processes()
    interesting = ("ConsoleWindowClass", "CASCADIA_HOSTING_WINDOW_CLASS",
                   "PseudoConsoleWindow", "Windows.UI.Core.CoreWindow")
    lines = []
    def _enum(hwnd, lparam):
        wpid = wintypes.DWORD(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
        cls = _get_class_name(hwnd)
        if wpid.value in target_pids or cls in interesting:
            exe = procs.get(wpid.value, (0, "?"))[1]
            vis = bool(user32.IsWindowVisible(hwnd))
            title = _get_window_text(hwnd)[:40]
            lines.append(f"    hwnd={hwnd} pid={wpid.value} exe={exe} "
                         f"class='{cls}' vis={vis} title='{title}'")
        return True
    user32.EnumWindows(WNDENUMPROC(_enum), 0)
    return lines

def find_console_hwnd(pid, timeout=FIND_WINDOW_TIMEOUT):
    """Acha a janela de console na arvore de processos do pid lancado."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        pids, procs = descendant_pids(pid)
        hwnd = _find_console_in_pids(pids)
        if hwnd:
            log(f"[find] console encontrado hwnd={hwnd} (pids da arvore={sorted(pids)})")
            return hwnd
        time.sleep(0.2)
    # falhou: diagnostico
    pids, procs = descendant_pids(pid)
    tree = {p: procs.get(p, (0, "?"))[1] for p in sorted(pids)}
    log(f"[find] FALHOU em {timeout}s. pid_lancado={pid} arvore={tree}")
    log("[find] dump de janelas relevantes:")
    for ln in dump_windows(pids):
        log(ln)
    return None


# ===========================================================================
# MOSTRAR / ESCONDER / TRAVAR O BOTAO FECHAR
# ===========================================================================
def disable_close_button(hwnd):
    """Remove o item 'Fechar' do menu do sistema => X desabilitado.
    Evita que o usuario MATE o operador clicando no X."""
    try:
        hmenu = user32.GetSystemMenu(hwnd, False)
        if hmenu:
            user32.DeleteMenu(hmenu, SC_CLOSE, MF_BYCOMMAND)
            user32.DrawMenuBar(hwnd)
            S.close_disabled = True
    except Exception:
        pass

def show_console():
    hwnd = S.console_hwnd
    if not hwnd or not user32.IsWindow(hwnd):
        # tenta relocalizar (ex.: apos um reinicio)
        if S.proc and S.proc.poll() is None:
            hwnd = find_console_hwnd(S.proc.pid, timeout=3.0)
            S.console_hwnd = hwnd
    if hwnd and user32.IsWindow(hwnd):
        user32.ShowWindow(hwnd, SW_SHOW)
        user32.ShowWindow(hwnd, SW_RESTORE)   # garante "normal" (caso estivesse minimizado)
        user32.SetForegroundWindow(hwnd)
        if not S.close_disabled:
            disable_close_button(hwnd)
    else:
        msgbox("A janela do console ainda nao esta disponivel.\n"
               "Tente novamente em alguns segundos.", APP_NAME)

def hide_console():
    hwnd = S.console_hwnd
    if hwnd and user32.IsWindow(hwnd):
        user32.ShowWindow(hwnd, SW_HIDE)


# ===========================================================================
# HOOK DE MINIMIZACAO: minimizar a janela => esconder (instantaneo)
# ===========================================================================
_win_event_hook = None
_win_event_proc_ref = None  # manter referencia viva (evita GC do callback)

def _on_min_event(hWinEventHook, event, hwnd, idObject, idChild, idThread, dwmsEventTime):
    try:
        if hwnd and S.console_hwnd and hwnd == S.console_hwnd:
            # esconde antes da animacao terminar => some pra bandeja
            user32.ShowWindow(hwnd, SW_HIDE)
    except Exception:
        pass

def win_event_loop():
    """Thread com o hook de minimizacao + bomba de mensagens."""
    global _win_event_hook, _win_event_proc_ref
    _win_event_proc_ref = WINEVENTPROC(_on_min_event)
    _win_event_hook = user32.SetWinEventHook(
        EVENT_SYSTEM_MINIMIZESTART, EVENT_SYSTEM_MINIMIZESTART,
        None, _win_event_proc_ref, 0, 0,
        WINEVENT_OUTOFCONTEXT | WINEVENT_SKIPOWNPROCESS
    )
    msg = wintypes.MSG()
    while not S.stopping:
        # GetMessage bloqueia; usamos timeout via PeekMessage seria mais complexo.
        # Aqui um GetMessage simples basta: ao encerrar, UnhookWinEvent + a thread
        # e daemon, entao o processo finaliza de qualquer forma.
        ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
        if ret == 0 or ret == -1:
            break
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))
    if _win_event_hook:
        user32.UnhookWinEvent(_win_event_hook)


# ===========================================================================
# KIOSK FOCUS GUARDIAN — garante que a janela Edge kiosk permaneça em foreground
# ===========================================================================
# MONITOR: vida do processo + relocalizar janela + watchdog opcional
# ===========================================================================
def monitor_loop(icon):
    while not S.stopping:
        try:
            # processo caiu?
            if S.proc is not None and S.proc.poll() is not None and not S.restarting:
                if WATCHDOG_AUTORESTART and not S.stopping:
                    _do_restart(icon, silent=True)
                # se nao tem autorestart, apenas seguimos (status mostrara "parado")
            # janela sumiu mas processo vivo? tenta relocalizar
            if (S.console_hwnd is None or not user32.IsWindow(S.console_hwnd)) \
               and S.proc is not None and S.proc.poll() is None and not S.restarting:
                hwnd = find_console_hwnd(S.proc.pid, timeout=2.0)
                if hwnd:
                    S.console_hwnd = hwnd
                    user32.ShowWindow(hwnd, SW_HIDE)
                    disable_close_button(hwnd)
        except Exception:
            pass
        time.sleep(MONITOR_INTERVAL)


# ===========================================================================
# STATUS DA CONEXAO (checagem independente + leitura de config.ini e do log;
# o supervisor NAO le o estado em memoria da TUI, mas o log/arquivo revela o
# estado real sem precisar de IPC)
# ===========================================================================
def tcp_ok(host, port, timeout=2.0):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False

def read_config_identity():
    """Le identificacao e alvos do config.ini ao lado do exe."""
    path = os.path.join(base_dir(), "config.ini")
    info = {
        "nome": "(sem nome)", "id": "(sem id)", "tipo": "(?)",
        "tasy_url": "", "host": "172.16.28.95", "porta": 5000,
        "separadas": False,
    }
    try:
        cp = configparser.ConfigParser()
        cp.read(path, encoding="utf-8")
        info["nome"] = cp.get("operador", "nome", fallback=info["nome"])
        info["id"] = cp.get("operador", "id", fallback=info["id"]) or "(sem id)"
        info["tipo"] = cp.get("operador", "tipo_cadastro", fallback=info["tipo"])
        info["separadas"] = cp.getboolean("operador", "usa_credenciais_separadas", fallback=False)
        info["tasy_url"] = cp.get("servidor", "tasy_url", fallback="")
        info["host"] = cp.get("servidor", "host", fallback=info["host"])
        info["porta"] = cp.getint("servidor", "porta", fallback=info["porta"])
    except Exception:
        pass
    return info

def tasy_reachable(tasy_url):
    """TCP no host do Tasy (porta da URL ou 443/80)."""
    try:
        u = urlparse(tasy_url)
        host = u.hostname
        if not host:
            return None
        port = u.port or (443 if (u.scheme or "https") == "https" else 80)
        return tcp_ok(host, port)
    except Exception:
        return None

def tail_log(n=4):
    """Ultimas n linhas do logs/operador.log do operador."""
    path = os.path.join(base_dir(), "logs", "operador.log")
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        return [ln.rstrip() for ln in lines[-n:] if ln.strip()]
    except Exception:
        return []

def uptime_str():
    if S.launched_at is None:
        return "?"
    secs = int((datetime.now() - S.launched_at).total_seconds())
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m}min"
    if m:
        return f"{m}min {s}s"
    return f"{s}s"

def show_status():
    def _check():
        proc_alive = (S.proc is not None and S.proc.poll() is None)
        idy = read_config_identity()
        host, port = idy["host"], idy["porta"]
        server_ok = tcp_ok(host, port)
        net_ok = tcp_ok("1.1.1.1", 443) or tcp_ok("8.8.8.8", 53)
        tasy_ok = tasy_reachable(idy["tasy_url"]) if idy["tasy_url"] else None
        logs = tail_log(4)

        def mark(b, ok="OK", no="FALHA", na="(n/d)"):
            return ok if b is True else (no if b is False else na)

        L = []
        L.append("== IDENTIFICACAO ==")
        L.append(f"Nome:   {idy['nome']}")
        L.append(f"ID:     {idy['id']}")
        L.append(f"Perfil: {idy['tipo']}"
                 + ("  (credenciais separadas)" if idy["separadas"] else ""))
        L.append("")
        L.append("== PROCESSO ==")
        if proc_alive:
            L.append(f"Operador: EM EXECUCAO  (PID {S.proc.pid}, ha {uptime_str()})")
        else:
            L.append("Operador: PARADO")
        L.append("")
        L.append("== CONEXOES ==")
        L.append(f"Servidor {host}:{port}: {mark(server_ok, 'ACESSIVEL', 'INACESSIVEL')}")
        L.append(f"Tasy ({urlparse(idy['tasy_url']).hostname or '-'}): {mark(tasy_ok)}")
        L.append(f"Internet: {mark(net_ok)}")
        if logs:
            L.append("")
            L.append("== ULTIMAS LINHAS DO LOG ==")
            L.extend(logs)
        L.append("")
        L.append("(Checagem do supervisor: processo + rede + log em arquivo. Para o")
        L.append(" painel completo em tempo real, use 'Abrir console'.)")
        msgbox("\n".join(L), f"{APP_NAME} - Status")
    threading.Thread(target=_check, daemon=True).start()


# ===========================================================================
# ACOES DO MENU
# ===========================================================================
def _do_restart(icon, silent=False):
    with S.lock:
        S.restarting = True
        try:
            old = S.proc
            S.console_hwnd = None
            S.close_disabled = False
            if old is not None:
                kill_tree(old.pid)
                try:
                    old.wait(timeout=5)
                except Exception:
                    pass
            time.sleep(0.5)
            ensure_conhost_default()
            # Libera restricoes de foreground antes de lancar o operador, para que
            # o Edge em kiosk consiga reclamar o primeiro plano ao reiniciar.
            unlock_foreground()
            S.proc = launch_operador()
            S.launched_at = datetime.now()
            if S.proc:
                hwnd = find_console_hwnd(S.proc.pid)
                S.console_hwnd = hwnd
                if hwnd:
                    user32.ShowWindow(hwnd, SW_HIDE)
                    disable_close_button(hwnd)
        finally:
            S.restarting = False
    if not silent:
        try:
            icon.notify("Operador reiniciado.", APP_NAME)
        except Exception:
            msgbox("Operador reiniciado.", APP_NAME)

def on_open(icon, item):   show_console()
def on_hide(icon, item):   hide_console()
def on_restart(icon, item): threading.Thread(target=_do_restart, args=(icon,), daemon=True).start()
def on_status(icon, item): show_status()

def on_exit(icon, item):
    S.stopping = True
    try:
        if S.proc is not None:
            kill_tree(S.proc.pid)
    except Exception:
        pass
    try:
        icon.stop()
    except Exception:
        pass


# ===========================================================================
# ICONE DA BANDEJA
# ===========================================================================
def load_tray_image():
    p = resource_path(APP_ICON_NAME)
    if p:
        try:
            return Image.open(p)
        except Exception:
            pass
    # fallback: desenha um icone simples
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((6, 6, 58, 58), fill=(40, 120, 220, 255))
    d.text((22, 20), "OP", fill=(255, 255, 255, 255))
    return img

def build_menu():
    return pystray.Menu(
        pystray.MenuItem("Abrir console",       on_open, default=True),  # duplo-clique
        pystray.MenuItem("Ocultar console",     on_hide),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Reiniciar operador",  on_restart),
        pystray.MenuItem("Ver status da conexao", on_status),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Sair do programa",    on_exit),
    )


# ===========================================================================
# INSTANCIA UNICA
# ===========================================================================
def ensure_single_instance():
    handle = kernel32.CreateMutexW(None, True, "Global\\TasyOperadorTraySupervisor")
    last = ctypes.get_last_error()
    if last == ERROR_ALREADY_EXISTS:
        msgbox("O Operador ja esta em execucao na bandeja do sistema.", APP_NAME)
        sys.exit(0)
    return handle  # manter vivo enquanto o processo roda


# ===========================================================================
# MAIN
# ===========================================================================
def main():
    _mutex = ensure_single_instance()  # noqa: F841 (mantem o mutex vivo)

    log("==== Operador Agent iniciado ====")
    log(f"[env] base_dir={base_dir()} frozen={getattr(sys,'frozen',False)}")

    # Forca o conhost como terminal padrao (corrige o handoff do Windows Terminal,
    # que quebra o mostrar/esconder do console). Reaplicado a cada boot.
    ensure_conhost_default()

    # --- Maquina ainda sem credenciais? Sobe VISIVEL para registro e encerra. ---
    # (No proximo boot, ja registrado, ele sobe oculto na bandeja.)
    if VISIBLE_IF_UNREGISTERED and not operador_is_ready():
        launch_operador_visible()
        return 0

    # Libera o foreground lock do Windows antes de lançar o operador.
    # No boot, o DWM pode estar inicializando e bloquear SetForegroundWindow;
    # este unlock garante que o Edge kiosk consiga esconder a barra de tarefas.
    unlock_foreground()

    # --- Maquina registrada: sobe OCULTO + bandeja ---
    # 1) sobe o operador oculto
    S.proc = launch_operador()
    if S.proc is None:
        return 1
    S.launched_at = datetime.now()

    # 2) acha a janela do console e garante oculto + X travado
    def _post_launch():
        hwnd = find_console_hwnd(S.proc.pid)
        if hwnd:
            S.console_hwnd = hwnd
            user32.ShowWindow(hwnd, SW_HIDE)
            disable_close_button(hwnd)
    threading.Thread(target=_post_launch, daemon=True).start()

    # 3) hook de minimizacao
    threading.Thread(target=win_event_loop, name="WinEventHook", daemon=True).start()

    # 4) icone da bandeja (bloqueia a main thread com seu proprio message loop)
    icon = pystray.Icon(APP_NAME, load_tray_image(), APP_TITLE, build_menu())

    # 5) monitor (precisa do icon p/ watchdog/notify)
    threading.Thread(target=monitor_loop, args=(icon,), name="Monitor", daemon=True).start()

    icon.run()  # roda ate on_exit chamar icon.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
