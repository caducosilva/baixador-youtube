@echo off
chcp 65001 >nul
title Capturar Login
cd /d "%~dp0"

:: usa o venv do projeto se existir; senao o Python do sistema
set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

%PY% "abrir_login.py" %*
echo.
pause
