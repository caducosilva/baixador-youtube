#!/usr/bin/env python3
"""Captura os cookies da janela de login e guarda para a automacao.

Por que assim: o Chrome/Edge cifram os cookies com App-Bound Encryption e o
yt-dlp nao consegue ler do disco (erro 'Failed to decrypt with DPAPI'). Aqui a
gente NAO tenta decifrar nada: pede os cookies ao proprio Chrome, pela porta de
depuracao (CDP). O Chrome entrega em texto limpo porque quem pergunta e um
cliente autorizado na mesma maquina.

Uso:
  python capturar_login.py            captura uma vez
  python capturar_login.py --esperar  espera voce logar e captura sozinho
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ytdl.comum import SITES, arquivo_cookie, garantir_pastas, carregar_config, preparar_console  # noqa: E402

PORTA_CDP = 9222
CDP_URL = f"http://127.0.0.1:{PORTA_CDP}"

# marcas que indicam sessao logada de verdade (nao so cookie de visitante)
MARCAS_LOGIN = {
    "youtube": ("SID", "SAPISID", "__Secure-1PSID", "LOGIN_INFO"),
    "tiktok": ("sessionid", "sid_tt", "uid_tt"),
    "instagram": ("sessionid", "ds_user_id"),
    "twitter": ("auth_token", "ct0"),
    "facebook": ("c_user", "xs"),
}


def dominio_do_site(site: str) -> list[str]:
    return SITES.get(site, [])


def pegar_cookies() -> list[dict]:
    """Le todos os cookies da janela aberta, via CDP."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        navegador = p.chromium.connect_over_cdp(CDP_URL, timeout=15000)
        try:
            cookies: list[dict] = []
            for ctx in navegador.contexts:
                cookies.extend(ctx.cookies())
            return cookies
        finally:
            navegador.close()


def para_netscape(cookies: list[dict]) -> str:
    """Converte para o formato Netscape que o yt-dlp entende."""
    linhas = [
        "# Netscape HTTP Cookie File",
        "# Gerado por capturar_login.py - NAO COMPARTILHE ESTE ARQUIVO",
        "",
    ]
    for c in cookies:
        dominio = c.get("domain", "")
        if not dominio:
            continue
        inclui_sub = "TRUE" if dominio.startswith(".") else "FALSE"
        caminho = c.get("path", "/")
        seguro = "TRUE" if c.get("secure") else "FALSE"
        expira = int(c.get("expires") or 0)
        if expira <= 0:
            expira = int(time.time()) + 365 * 24 * 3600  # cookie de sessao: 1 ano
        nome = c.get("name", "")
        valor = c.get("value", "")
        linhas.append(f"{dominio}\t{inclui_sub}\t{caminho}\t{seguro}\t{expira}\t{nome}\t{valor}")
    return "\n".join(linhas) + "\n"


def separar_por_site(cookies: list[dict]) -> dict[str, list[dict]]:
    saida: dict[str, list[dict]] = {s: [] for s in SITES}
    for c in cookies:
        dominio = (c.get("domain") or "").lstrip(".").lower()
        for site, dominios in SITES.items():
            if any(dominio == d or dominio.endswith("." + d) for d in dominios):
                saida[site].append(c)
                break
    return saida


def esta_logado(site: str, cookies: list[dict]) -> bool:
    nomes = {c.get("name") for c in cookies}
    return any(m in nomes for m in MARCAS_LOGIN.get(site, ()))


def salvar(por_site: dict[str, list[dict]], verboso: bool = True) -> int:
    salvos = 0
    for site, cookies in por_site.items():
        if not cookies:
            continue
        destino = arquivo_cookie(site)
        destino.write_text(para_netscape(cookies), encoding="utf-8")
        logado = esta_logado(site, cookies)
        if logado:
            salvos += 1
        if verboso:
            marca = "LOGADO  " if logado else "sem login"
            print(f"    {marca}  {site:11} {len(cookies):3} cookies -> cookies/{site}.txt")
    return salvos


def main() -> int:
    preparar_console()
    garantir_pastas(carregar_config())
    esperar = "--esperar" in sys.argv

    print("\n" + "=" * 66)
    print("  CAPTURAR LOGIN DA JANELA ABERTA")
    print("=" * 66)

    try:
        import playwright  # noqa: F401
    except ImportError:
        print("\n  ERRO: playwright nao instalado. Rode:  pip install playwright")
        return 1

    if esperar:
        print("\n  Aguardando voce fazer login na janela do Chrome...")
        print("  (verificando a cada 10s; Ctrl+C para parar)\n")
        limite = time.time() + 20 * 60
        ultimo = -1
        while time.time() < limite:
            try:
                cookies = pegar_cookies()
            except Exception as exc:
                print(f"  janela nao encontrada ({str(exc)[:60]}); tentando de novo...")
                time.sleep(10)
                continue
            por_site = separar_por_site(cookies)
            logados = [s for s, c in por_site.items() if esta_logado(s, c)]
            if len(logados) != ultimo:
                ultimo = len(logados)
                print(f"  [{time.strftime('%H:%M:%S')}] logins detectados: {logados or 'nenhum ainda'}")
            if logados:
                salvar(por_site, verboso=False)
            time.sleep(10)
        print("\n  Tempo esgotado.")

    try:
        cookies = pegar_cookies()
    except Exception as exc:
        print(f"\n  ERRO: nao consegui falar com a janela do Chrome.\n  {str(exc)[:200]}")
        print(f"\n  A janela precisa ter sido aberta com --remote-debugging-port={PORTA_CDP}.")
        print("  Use o atalho CAPTURAR-LOGIN.bat, que abre do jeito certo.")
        return 1

    print(f"\n  {len(cookies)} cookies lidos da janela.\n")
    por_site = separar_por_site(cookies)
    logados = salvar(por_site)

    print("\n" + "-" * 66)
    if logados:
        print(f"  PRONTO: {logados} site(s) com login salvo.")
        print("  A automacao ja vai usar esses cookies nos proximos downloads.")
        print("  O yt-dlp renova a sessao sozinho a cada uso.")
    else:
        print("  Nenhum login detectado. Entre nas contas na janela e rode de novo.")
    print("-" * 66 + "\n")
    return 0 if logados else 1


if __name__ == "__main__":
    raise SystemExit(main())
