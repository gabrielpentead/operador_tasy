@echo off
title Instalar Operador na Inicializacao

set "PASTA=C:\operador_tasy"
set "EXE=%PASTA%\operador_agent.exe"
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "LINK=%STARTUP%\Operador Agent.lnk"

echo ==========================================
echo  Instalando operador na inicializacao
echo ==========================================

REM Verifica se o executavel existe
if not exist "%EXE%" (
    echo ERRO: nao encontrei operador_agent.exe em:
    echo %EXE%
    pause
    exit /b
)

REM Remove atalho antigo se existir
if exist "%LINK%" (
    echo Removendo atalho antigo...
    del "%LINK%"
)

REM Cria atalho via PowerShell
echo Criando atalho de inicializacao...

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
"$s=(New-Object -COM WScript.Shell).CreateShortcut('%LINK%'); ^
$s.TargetPath='%EXE%'; ^
$s.WorkingDirectory='%PASTA%'; ^
$s.WindowStyle=7; ^
$s.Save()"

echo.
echo OK! Operador adicionado na inicializacao.
echo Caminho: %EXE%
echo.
pause