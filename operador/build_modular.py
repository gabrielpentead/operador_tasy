#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🏥 CLIENTE OPERADOR TASY - BUILD MODULAR
Script para criar executável do sistema modular

Autor: Núcleo de Tecnologia da Informação - Hospital São Vicente
Data: 21/04/2026
Versão: 1.5.5
"""

import os
import sys
import subprocess
import shutil
import platform
from pathlib import Path

def log(message):
    """Log com timestamp"""
    from datetime import datetime
    timestamp = datetime.now().strftime("[%H:%M:%S]")
    print(f"{timestamp} {message}")

def verificar_python():
    """Verifica versão do Python"""
    version = sys.version_info
    if version.major != 3 or version.minor < 8:
        log("❌ Python 3.8+ é necessário")
        return False
    
    log(f"\u2705 Python {version.major}.{version.minor}.{version.micro} detectado")
    return True

def verificar_pathlib_conflito():
    """Verifica e remove o pacote pathlib obsoleto que causa conflito"""
    try:
        import importlib.util
        spec = importlib.util.find_spec('pathlib')
        if spec and hasattr(spec, 'origin') and spec.origin:
            # Verificar se é o pacote pathlib obsoleto (não built-in)
            if 'site-packages' in spec.origin:
                log("⚠️  Pacote pathlib obsoleto detectado")
                log("   Removendo pacote que causa conflito com PyInstaller...")
                
                result = subprocess.run([
                    sys.executable, '-m', 'pip', 'uninstall', 'pathlib', '-y'
                ], capture_output=True, text=True)
                
                if result.returncode == 0:
                    log("✅ Pacote pathlib obsoleto removido com sucesso")
                else:
                    log("⚠️  Não foi possível remover pathlib automaticamente")
                    log("   Execute manualmente: python -m pip uninstall pathlib -y")
                    
    except Exception:
        # Se não conseguir verificar, continuar
        pass

def instalar_dependencias():
    """Instala dependências necessárias"""
    # Verificar e remover pathlib obsoleto primeiro
    verificar_pathlib_conflito()
    
    dependencias = [
        'pyinstaller>=5.0',
        'python-socketio[client]>=5.9.0',
        'selenium>=4.10.0',
        'psutil>=5.9.0',
        'requests>=2.31.0',
        'pillow>=8.0.0',  # Necessário para processamento de ícones
        'schedule>=1.1.0', # Para agendamento de tarefas
        'screeninfo>=0.8.1', # Para detectar múltiplos monitores
        'textual>=0.40.0' # Interface de console moderna (substitui rich puro)
    ]
    
    for dep in dependencias:
        log(f"Instalando {dep}...")
        result = subprocess.run([
            sys.executable, '-m', 'pip', 'install', dep
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            log(f"❌ ERRO ao instalar {dep}")
            log(f"   {result.stderr}")
            return False
    
    log("✅ Todas as dependências instaladas")
    return True

def verificar_estrutura():
    """Verifica se a estrutura modular está presente"""
    base_dir = Path(__file__).parent
    
    diretorios_necessarios = [
        'core',
        'automation',
        'communication',
        'utils'
    ]
    
    arquivos_necessarios = [
        'tasy_operador_modular.py',
        'core/client.py',
        'core/config.py', 
        'core/crypto.py',
        'core/logging_setup.py',
        'automation/tasy_automation.py',
        'automation/browser_manager.py',
        'automation/voice_manager.py',
        'automation/selenium_utils.py',
        'communication/websocket_client.py',
        'communication/server_api.py',
        'utils/constants.py',
        'utils/system_utils.py'
    ]
    
    # Verificar diretórios
    for diretorio in diretorios_necessarios:
        path = base_dir / diretorio
        if not path.exists():
            log(f"❌ Diretório ausente: {diretorio}")
            return False
        
        # Verificar __init__.py
        init_file = path / '__init__.py'
        if not init_file.exists():
            log(f"❌ Arquivo __init__.py ausente em: {diretorio}")
            return False
    
    # Verificar arquivos
    for arquivo in arquivos_necessarios:
        path = base_dir / arquivo
        if not path.exists():
            log(f"❌ Arquivo ausente: {arquivo}")
            return False
    
    log("✅ Estrutura modular verificada")
    return True

def criar_spec_file():
    """Cria arquivo .spec para PyInstaller"""
    
    # Verificar arquivos opcionais
    datas_list = [
        ('core', 'core'),
        ('automation', 'automation'),
        ('communication', 'communication'),
        ('utils', 'utils'),
        ('build', 'build')
    ]
    
    # Adicionar arquivos opcionais se existirem
    if os.path.exists('config.ini.template'):
        datas_list.append(('config.ini.template', '.'))
    if os.path.exists('operador.py'):
        datas_list.append(('operador.py', '.'))
    if os.path.exists('tasy_automation.py'):
        datas_list.append(('tasy_automation.py', '.'))
    
    # Configurar ícone
    icon_config = "icon='app.ico'" if os.path.exists('app.ico') else "icon=None"
    
    spec_content = f'''# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['tasy_operador_modular.py'],
    pathex=[],
    binaries=[],
    datas={datas_list},
    hiddenimports=[
        'socketio',
        'socketio.client',
        'engineio',
        'engineio.client',
        'selenium',
        'selenium.webdriver',
        'selenium.webdriver.edge',
        'selenium.webdriver.edge.service',
        'selenium.webdriver.edge.options',
        # Selenium 4.44 carrega o Edge por import tardio (__getattr__). Sem
        # listar o webdriver explicitamente, o PyInstaller não o empacota e a
        # automação quebra em runtime com "No module named
        # selenium.webdriver.edge.webdriver".
        'selenium.webdriver.edge.webdriver',
        'selenium.webdriver.remote.webdriver',
        'selenium.webdriver.common.service',
        'psutil',
        'requests',
        'configparser',
        'pathlib',
        'uuid',
        'platform',
        'socket',
        'base64',
        'logging',
        'threading',
        'time',
        'datetime',
        'json',
        'os',
        'sys',
        'subprocess',
        'shutil',
        'tempfile',
        'textual',
        'textual.app',
        'textual.widgets',
        'textual.containers',
        'textual.reactive',
        'textual.screen',
        'core',
        'core.client',
        'core.config',
        'core.crypto',
        'core.logging_setup',
        'automation',
        'automation.tasy_automation',
        'automation.browser_manager',
        'automation.voice_manager',
        'automation.selenium_utils',
        'communication',
        'communication.websocket_client',
        'communication.server_api',
        'utils',
        'utils.constants',
        'utils.system_utils'
    ],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='operador',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_info=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    {icon_config}
)
'''
    
    with open('tasy_operador_modular.spec', 'w', encoding='utf-8') as f:
        f.write(spec_content)
    
    log("✅ Arquivo .spec criado")
    return True

def criar_scripts_batch(dist_path):
    """Cria os arquivos .bat necessários dentro da pasta dist"""
    log("-> Criando scripts .bat na pasta dist...")

    # --- Conteúdo para iniciar_operador.bat ---
    iniciar_content = """@echo off
echo Iniciando o Operador do Painel de Senhas...
start "" operador.exe
"""
    try:
        with open(dist_path / 'iniciar_operador.bat', 'w', encoding='utf-8') as f:
            f.write(iniciar_content)
        log("   ✅ iniciar_operador.bat criado.")
    except Exception as e:
        log(f"   ❌ Erro ao criar iniciar_operador.bat: {e}")
        return False

    # --- Conteúdo para instalar.bat ---
    instalar_content = """@echo off
setlocal

REM --- Configuracoes ---
set "ShortcutName=Painel de Senhas HSV.lnk"
set "BatchToRun=iniciar_operador.bat"
set "ExeToRun=operador.exe"
REM ---------------------

REM Pega o diretorio do script atual (que sera a pasta 'dist')
set "ScriptDir=%~dp0"
set "TargetBatchPath=%ScriptDir%%BatchToRun%"
set "TargetExePath=%ScriptDir%%ExeToRun%"
set "StartupFolderPath=%appdata%\\Microsoft\\Windows\\Start Menu\\Programs\\Startup"
set "ShortcutPath=%StartupFolderPath%\\%ShortcutName%"

echo.
echo    +-------------------------------------------+
echo    ^|    Instalador do Operador Painel Senhas   ^|
echo    +-------------------------------------------+
echo.

if not exist "%TargetBatchPath%" (
    echo ERRO: Arquivo '%BatchToRun%' nao encontrado.
    pause
    exit /b 1
)

echo Criando atalho para inicializacao automatica com o Windows...

set "VBS_SCRIPT=%TEMP%\\create_shortcut.vbs"
echo Set oWS = WScript.CreateObject("WScript.Shell") > "%VBS_SCRIPT%"
echo sLinkFile = "%ShortcutPath%" >> "%VBS_SCRIPT%"
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> "%VBS_SCRIPT%"
echo oLink.TargetPath = "%TargetBatchPath%" >> "%VBS_SCRIPT%"
echo oLink.Description = "Inicia o Operador do Painel de Senhas HSV" >> "%VBS_SCRIPT%"
echo oLink.IconLocation = "%TargetExePath%, 0" >> "%VBS_SCRIPT%"
echo oLink.WorkingDirectory = "%ScriptDir%" >> "%VBS_SCRIPT%"
echo oLink.Save >> "%VBS_SCRIPT%"

cscript //nologo "%VBS_SCRIPT%"
if exist "%VBS_SCRIPT%" del "%VBS_SCRIPT%"

if exist "%ShortcutPath%" (
    echo ... Atalho criado com sucesso na pasta de inicializacao.
) else (
    echo ... ERRO: Nao foi possivel criar o atalho.
    echo    Tente executar este instalador como Administrador.
    pause
    exit /b 1
)

echo.
echo Instalacao concluida! Iniciando a aplicacao...
start "" "%TargetBatchPath%"

echo.
echo O instalador sera auto-destruido agora.
timeout /t 3 /nobreak >nul

(goto) 2>nul & del "%~f0"
endlocal
"""
    try:
        with open(dist_path / 'instalar.bat', 'w', encoding='utf-8') as f:
            f.write(instalar_content)
        log("   ✅ instalar.bat criado.")
    except Exception as e:
        log(f"   ❌ Erro ao criar instalar.bat: {e}")
        return False

    return True

def executar_build():
    """Executa o build com PyInstaller"""
    log("🔨 Iniciando build do executável...")
    
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--clean',
        '--noconfirm',
        'tasy_operador_modular.spec'
    ]
    
    log(f"Executando: {' '.join(cmd)}")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        log("✅ Build concluído com sucesso")
        
        # Verificar se executável foi criado
        exe_path = Path('dist/operador.exe')
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            log(f"✅ Executável criado: {exe_path}")
            log(f"   Tamanho: {size_mb:.1f} MB")
            
            if not criar_scripts_batch(Path('dist')):
                log("❌ Falha ao criar scripts .bat.")
                return False
            
            return True
        else:
            log("❌ Executável não foi encontrado após build")
            return False
    else:
        log("❌ ERRO durante o build")
        log(result.stdout)
        log(result.stderr)
        return False

def limpar_arquivos_temporarios():
    """Remove arquivos temporários do build"""
    log("🧹 Limpando arquivos temporários...")
    
    arquivos_para_remover = [
        'tasy_operador_modular.spec',
        'build'
    ]
    
    for item in arquivos_para_remover:
        try:
            path = Path(item)
            if path.exists():
                if path.is_file():
                    path.unlink()
                    log(f"   Removido: {item}")
                elif path.is_dir():
                    shutil.rmtree(path)
                    log(f"   Removido: {item}")
        except Exception as e:
            log(f"   ⚠️ Erro ao remover {item}: {e}")

def main():
    """Função principal"""
    if platform.system() != "Windows":
        log("❌ Este script é destinado apenas para Windows.")
        return 1

    print("\U0001f3e5 CLIENTE OPERADOR TASY - BUILD MODULAR")
    print("="*50)
    
    # Verificações iniciais
    if not verificar_python():
        return 1
    
    if not verificar_estrutura():
        return 1
    
    # Confirmar build
    if '-y' not in sys.argv and '--yes' not in sys.argv:
        resposta = input("\n🔨 Deseja continuar com o build? (s/n): ").strip().lower()
        if resposta not in ['s', 'sim', 'y', 'yes']:
            log("❌ Build cancelado pelo usuário")
            return 1
    
    try:
        # Instalar dependências
        if not instalar_dependencias():
            return 1
        
        # Criar arquivo .spec
        if not criar_spec_file():
            return 1
        
        # Executar build
        if not executar_build():
            return 1
        
        # Limpar arquivos temporários
        limpar_arquivos_temporarios()
        
        print("\n🎉 BUILD CONCLUÍDO COM SUCESSO!")
        print("📦 Executável: dist/Tasy_Operador_Modular.exe")
        print("💡 Teste o executável antes de distribuir")
        
        return 0
        
    except KeyboardInterrupt:
        log("\n🛑 Build interrompido pelo usuário")
        return 1
    except Exception as e:
        log(f"\n❌ ERRO INESPERADO: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
