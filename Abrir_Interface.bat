@echo off
title Baixador de Músicas e Vídeos
cd /d "%~dp0"

start "" pythonw app.py

if %ERRORLEVEL% NEQ 0 (
    python app.py
)
