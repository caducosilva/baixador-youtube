@echo off
title Login YouTube - Captura de Cookies
chcp 65001 > nul
cd /d "%~dp0"

echo ========================================================
echo               LOGIN YOUTUBE / GOOGLE
echo ========================================================
echo.
echo Abrindo o Chrome em perfil separado...
echo Apos fazer login nas abas abertas, volte aqui e aperte ENTER.
echo.

python abrir_login.py

pause
