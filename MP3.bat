@echo off
chcp 65001 >nul
title Baixar MP3
cd /d "%~dp0"

:: usa o venv do projeto se existir; senao o Python do sistema
set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

%PY% "baixar_mp3.py" %*
echo.
pause
