#!/usr/bin/env python3
"""Configuracao, cookies e utilidades compartilhadas.

O ponto delicado aqui e o LOGIN. Existem dois jeitos de o yt-dlp usar a sua
conta, e eles falham de formas diferentes no Windows:

1. --cookies-from-browser  : le direto do navegador. Comodo, mas o Chrome/Edge
   recentes cifram os cookies com "App-Bound Encryption" e travam o banco
   enquanto o navegador esta aberto -> costuma falhar.
2. --cookies arquivo.txt   : le de um arquivo no formato Netscape. Sempre
   funciona, e o yt-dlp REGRAVA o arquivo com a sessao renovada, que e
   exatamente o "guardar meu login" que voce quer.

A estrategia daqui: usa o arquivo se existir; se nao, tenta o navegador; e
guarda o resultado no arquivo para as proximas vezes.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CONFIG_PATH = RAIZ / "config.json"
COOKIES_DIR = RAIZ / "cookies"
LOGS_DIR = RAIZ / "logs"

PADRAO = {
    # "~" e expandido para a pasta do usuario em tempo de execucao, entao o
    # mesmo config.json funciona em qualquer maquina/usuario
    "pasta_mp3": "~/Music",
    "pasta_mp4": "~/Videos/VideoDownloader",
    # MP4 sai com nome aleatorio (UUID) e sem metadado nenhum
    "nome_aleatorio_mp4": True,
    "remover_metadados_mp4": True,
    "navegador_cookies": "firefox",
    "perfil_navegador": "",
    "qualidade_mp3": "0",
    "altura_maxima_mp4": 1080,
    # "auto" = se a URL for de playlist/canal/perfil, baixa tudo;
    # se for de um video so, baixa so ele. true = sempre; false = nunca.
    "incluir_playlist": "auto",
    "limite_itens_playlist": 0,   # 0 = sem limite
    "pasta_por_playlist": True,   # cria subpasta com o nome da playlist
    "numerar_playlist": True,     # prefixo 01 - , 02 - ...
    "usar_historico": True,       # nao rebaixa o que ja foi baixado
    "escrever_thumbnail": True,
    "escrever_metadados": True,
    "limite_downloads_simultaneos": 3,
    "idioma_legendas": "pt",
    "baixar_legendas": False,
}

# cada site guarda seu proprio cookie
SITES = {
    # google.com entra junto: os cookies de sessao (SID, SAPISID, __Secure-1PSID)
    # ficam em .google.com, nao em .youtube.com. Sem eles o yt-dlp segue anonimo.
    "youtube": ["youtube.com", "youtu.be", "music.youtube.com", "google.com"],
    "tiktok": ["tiktok.com", "vm.tiktok.com"],
    "instagram": ["instagram.com"],
    "twitter": ["twitter.com", "x.com"],
    "facebook": ["facebook.com", "fb.watch"],
}


def preparar_console() -> None:
    """Console do Windows em cp1252 quebra com acento/emoji do yt-dlp."""
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass


def expandir(caminho: str) -> str:
    """Resolve '~' e variaveis de ambiente para um caminho absoluto real."""
    return str(Path(os.path.expandvars(str(caminho))).expanduser())


def carregar_config() -> dict:
    cfg = dict(PADRAO)
    if CONFIG_PATH.exists():
        try:
            cfg.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
        except Exception as exc:  # noqa: BLE001
            print(f"AVISO: config.json invalido ({exc}); usando padroes.")
    for chave in ("pasta_mp3", "pasta_mp4"):
        cfg[chave] = expandir(cfg.get(chave) or PADRAO[chave])
    return cfg


def salvar_config(cfg: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def garantir_pastas(cfg: dict) -> None:
    for chave in ("pasta_mp3", "pasta_mp4"):
        Path(cfg[chave]).mkdir(parents=True, exist_ok=True)
    COOKIES_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)


def site_da_url(url: str) -> str:
    baixo = url.lower()
    for site, dominios in SITES.items():
        if any(d in baixo for d in dominios):
            return site
    return "outros"


def eh_playlist(url: str) -> bool:
    """A URL aponta para varios itens (playlist, album, canal, perfil)?

    Testado: youtube.com/playlist?list=, music.youtube.com/playlist?list=,
    /@canal/videos, /channel/..., e perfil do TikTok (/@user sem /video/).
    """
    baixo = url.lower()
    if "list=" in baixo or "/playlist" in baixo or "/sets/" in baixo:
        return True
    if any(m in baixo for m in ("/channel/", "/c/", "/user/")):
        return True
    if "/videos" in baixo or "/shorts" in baixo and "/shorts/" not in baixo:
        return True
    # perfil do TikTok: tiktok.com/@alguem  (mas nao .../video/123)
    if "tiktok.com/@" in baixo and "/video/" not in baixo:
        return True
    # canal do YouTube: youtube.com/@alguem  (sem /watch)
    if "youtube.com/@" in baixo and "/watch" not in baixo:
        return True
    return False


def deve_baixar_playlist(url: str, cfg: dict, forcado: bool | None = None) -> bool:
    """forcado vem da linha de comando (--playlist / --so-um) e vence tudo."""
    if forcado is not None:
        return forcado
    modo = cfg.get("incluir_playlist", "auto")
    if isinstance(modo, bool):
        return modo
    if str(modo).lower() == "auto":
        return eh_playlist(url)
    return False


def separar_opcoes(argv: list[str]) -> tuple[list[str], bool | None]:
    """Separa URLs de opcoes. Devolve (urls, forcar_playlist).

    --playlist / -p  : baixa a playlist inteira mesmo que o link pareca de um item
    --so-um / -1     : baixa so o item, mesmo que o link tenha lista
    """
    urls: list[str] = []
    forcado: bool | None = None
    for arg in argv:
        baixo = arg.strip().lower()
        if baixo in ("--playlist", "-p", "/playlist"):
            forcado = True
        elif baixo in ("--so-um", "--um", "-1", "/um"):
            forcado = False
        elif arg.strip():
            urls.append(arg.strip())
    return urls, forcado


def arquivo_cookie(site: str) -> Path:
    return COOKIES_DIR / f"{site}.txt"


def cookie_valido(caminho: Path) -> bool:
    """Arquivo Netscape com pelo menos uma linha de cookie de verdade."""
    if not caminho.exists() or caminho.stat().st_size < 50:
        return False
    try:
        for linha in caminho.read_text(encoding="utf-8", errors="replace").splitlines():
            if linha.strip() and not linha.startswith("#") and "\t" in linha:
                return True
    except Exception:  # noqa: BLE001
        return False
    return False


def opcoes_de_login(url: str, cfg: dict, verboso: bool = True) -> dict:
    """Devolve as opcoes de cookie do yt-dlp para esta URL.

    Prioridade: arquivo salvo > navegador. O arquivo vence porque nao depende
    do navegador estar fechado e sobrevive ao App-Bound Encryption.
    """
    site = site_da_url(url)
    alvo = arquivo_cookie(site)

    if cookie_valido(alvo):
        if verboso:
            print(f"  login: usando cookies salvos de '{site}' ({alvo.name})")
        # cookiefile faz o yt-dlp LER e tambem REGRAVAR a sessao renovada
        return {"cookiefile": str(alvo)}

    navegador = (cfg.get("navegador_cookies") or "").strip()
    # so tenta o navegador se ele existir de fato; senao o yt-dlp aborta o download
    if navegador and navegador not in navegadores_instalados():
        alternativo = navegador_padrao()
        if verboso:
            print(f"  login: '{navegador}' nao esta instalado", end="")
            print(f"; usando '{alternativo}'" if alternativo else "; seguindo sem login")
        navegador = alternativo

    if navegador:
        perfil = (cfg.get("perfil_navegador") or "").strip()
        if verboso:
            extra = f" (perfil: {perfil})" if perfil else ""
            print(f"  login: tentando ler cookies do {navegador}{extra}")
        return {"cookiesfrombrowser": (navegador, perfil or None, None, None)}

    if verboso:
        print("  login: nenhum cookie configurado (so conteudo publico)")
    return {}


PASTAS_NAVEGADOR = {
    "firefox": r"Mozilla\Firefox\Profiles",
    "chrome": r"Google\Chrome\User Data",
    "edge": r"Microsoft\Edge\User Data",
    "brave": r"BraveSoftware\Brave-Browser\User Data",
    "opera": r"Opera Software\Opera Stable",
    "vivaldi": r"Vivaldi\User Data",
    "chromium": r"Chromium\User Data",
}


def navegadores_instalados() -> list[str]:
    """So oferece navegadores que existem na maquina."""
    import os

    bases = [os.environ.get("LOCALAPPDATA", ""), os.environ.get("APPDATA", "")]
    achados = []
    for nome, sufixo in PASTAS_NAVEGADOR.items():
        for base in bases:
            if base and (Path(base) / sufixo).exists():
                achados.append(nome)
                break
    return achados


def navegador_padrao() -> str:
    """Escolhe um navegador que realmente existe (Firefox primeiro: cookies mais faceis)."""
    instalados = navegadores_instalados()
    for preferido in ("firefox", "chrome", "edge", "brave", "vivaldi", "opera", "chromium"):
        if preferido in instalados:
            return preferido
    return ""


def formatar_bytes(n: float | None) -> str:
    if not n:
        return "?"
    for unidade in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unidade}"
        n /= 1024
    return f"{n:.1f} TB"
