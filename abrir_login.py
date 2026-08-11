#!/usr/bin/env python3
"""Abre a janela de login e captura os cookies quando voce terminar.

Usa um PERFIL SEPARADO do seu Chrome do dia a dia. Isso e proposital:
  * o Chrome bloqueia a porta de depuracao no perfil padrao (protecao contra
    roubo de cookies por outros programas);
  * assim sua navegacao normal fica intocada;
  * e este perfil guarda o login para as proximas capturas.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

PERFIL = RAIZ / "chrome-login-profile"
PORTA = 9222
SITES_LOGIN = [
    "https://accounts.google.com/",
    "https://www.tiktok.com/login",
    "https://www.instagram.com/accounts/login/",
]


def chrome_exe() -> Path | None:
    for base in (os.environ.get("ProgramFiles", ""), os.environ.get("ProgramFiles(x86)", ""),
                 os.environ.get("LOCALAPPDATA", "")):
        if not base:
            continue
        p = Path(base) / "Google" / "Chrome" / "Application" / "chrome.exe"
        if p.exists():
            return p
    return None


def porta_ativa() -> bool:
    import socket

    try:
        with socket.create_connection(("127.0.0.1", PORTA), timeout=1.5):
            return True
    except Exception:
        return False


def main() -> int:
    from ytdl.comum import preparar_console

    preparar_console()
    chrome = chrome_exe()
    if not chrome:
        print("ERRO: Chrome nao encontrado.")
        return 1

    PERFIL.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 68)
    print("  JANELA DE LOGIN — seus cookies ficam so no seu PC")
    print("=" * 68)

    if porta_ativa():
        print("\n  Ja existe uma janela de login aberta.")
    else:
        print(f"\n  Abrindo Chrome com perfil separado:\n    {PERFIL}\n")
        subprocess.Popen(
            [
                str(chrome),
                f"--user-data-dir={PERFIL}",
                f"--remote-debugging-port={PORTA}",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-background-mode",
                *SITES_LOGIN,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(30):
            time.sleep(1)
            if porta_ativa():
                break

    if not porta_ativa():
        print("  ERRO: a janela nao abriu a porta de depuracao.")
        return 1

    print("  " + "-" * 64)
    print("  AGORA E COM VOCE:")
    print("    1. faca login nas abas que abriram (Google/YouTube, TikTok, Instagram)")
    print("    2. volte aqui e aperte ENTER")
    print("    3. NAO feche a janela do Chrome antes disso")
    print("  " + "-" * 64)
    input("\n  Aperte ENTER quando tiver terminado os logins... ")

    from capturar_login import (  # noqa: E402
        pegar_cookies,
        salvar,
        separar_por_site,
    )

    try:
        cookies = pegar_cookies()
    except Exception as exc:
        print(f"\n  ERRO ao ler a janela: {str(exc)[:200]}")
        print("  A janela do Chrome ainda esta aberta? Tente de novo.")
        return 1

    print(f"\n  {len(cookies)} cookies lidos.\n")
    por_site = separar_por_site(cookies)
    logados = salvar(por_site)

    print("\n" + "-" * 68)
    if logados:
        print(f"  PRONTO: {logados} site(s) com login guardado.")
        print("  Pode fechar a janela. Os downloads ja vao usar esse login.")
    else:
        print("  Nenhum login detectado — parece que as contas nao foram conectadas.")
        print("  Deixe a janela aberta, faca login e rode este atalho de novo.")
    print("-" * 68 + "\n")
    return 0 if logados else 1


if __name__ == "__main__":
    raise SystemExit(main())
