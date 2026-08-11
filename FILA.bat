@echo off
chcp 65001 >nul
title Fila de Downloads
cd /d "%~dp0"

:: usa o venv do projeto se existir; senao o Python do sistema
set "PY=pythonw"
if exist ".venv\Scripts\pythonw.exe" set "PY=.venv\Scripts\pythonw.exe"

start "" %PY% "interface.py"
