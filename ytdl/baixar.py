#!/usr/bin/env python3
"""Motor de download usado pelo modo MP3 e pelo modo MP4."""

from __future__ import annotations

import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

from . import historico
from .comum import (
    LOGS_DIR,
    carregar_config,
    deve_baixar_playlist,
    formatar_bytes,
    garantir_pastas,
    opcoes_de_login,
    site_da_url,
)

try:
    from yt_dlp import YoutubeDL
    from yt_dlp.utils import DownloadError
except ImportError:  # pragma: no cover
    print("ERRO: yt-dlp nao esta instalado. Rode:  pip install -U yt-dlp")
    raise SystemExit(1)


class Progresso:
    """Barra de progresso enxuta (o padrao do yt-dlp polui muito o console).

    No terminal usa '\\r' para reescrever a mesma linha. Quando a saida NAO e
    um terminal (caso da fila, que le o processo por pipe), '\\r' nunca fecha a
    linha e quem le fica sem novidade - por isso ali imprimimos linhas de
    verdade, limitadas no tempo para nao inundar o log.
    """

    def __init__(self) -> None:
        self.ultimo = ""
        self.ultimo_envio = 0.0
        self.terminal = sys.stdout.isatty()

    def _rotulo_playlist(self, d: dict) -> str:
        info = d.get("info_dict") or {}
        idx = info.get("playlist_index")
        total = info.get("n_entries") or info.get("playlist_count")
        if idx and total:
            return f"[{idx}/{total}] "
        if idx:
            return f"[{idx}] "
        return ""

    def __call__(self, d: dict) -> None:
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            baixado = d.get("downloaded_bytes") or 0
            vel = d.get("speed")
            pct = f"{baixado / total * 100:5.1f}%" if total else "  ?  "
            marca = self._rotulo_playlist(d)
            linha = f"    {marca}{pct}  {formatar_bytes(baixado)}/{formatar_bytes(total)}"
            if vel:
                linha += f"  a {formatar_bytes(vel)}/s"

            if self.terminal:
                if linha != self.ultimo:
                    print(linha.ljust(74), end="\r", flush=True)
                    self.ultimo = linha
                return

            # sem terminal: linha inteira, no maximo 1 por segundo
            agora = time.time()
            if agora - self.ultimo_envio >= 1.0 and linha != self.ultimo:
                print(linha, flush=True)
                self.ultimo = linha
                self.ultimo_envio = agora

        elif d["status"] == "finished":
            marca = self._rotulo_playlist(d)
            if self.terminal:
                print(" " * 76, end="\r")
            print(f"    {marca}baixado; convertendo...", flush=True)
            self.ultimo = ""
            self.ultimo_envio = 0.0


def _modelo_saida(pasta: str, cfg: dict, playlist: bool, modo: str = "mp4") -> str:
    """Onde e como nomear o arquivo.

    MP3 solto:  Pasta/Titulo.mp3
    MP4 solto:  Pasta/Uploader - Titulo [id].mp4 (garante unicidade em Reels/Shorts)
    Playlist:   Pasta/Nome da Playlist/Titulo.ext
    """
    base = Path(pasta)
    if not playlist:
        if modo == "mp3":
            return str(base / "%(title)s.%(ext)s")
        return str(base / "%(uploader&{} - |)s%(title)s [%(id)s].%(ext)s")

    if cfg.get("pasta_por_playlist", True):
        base = base / "%(playlist_title,playlist|Downloads)s"
    if cfg.get("numerar_playlist", False):
        nome = "%(playlist_index)02d - %(title)s.%(ext)s" if modo == "mp3" else "%(playlist_index)02d - %(title)s [%(id)s].%(ext)s"
    else:
        nome = "%(title)s.%(ext)s" if modo == "mp3" else "%(uploader&{} - |)s%(title)s [%(id)s].%(ext)s"
    return str(base / nome)


def opcoes_mp3(cfg: dict, url: str, playlist: bool = False) -> dict:
    opts = {
        "format": "bestaudio/best",
        "outtmpl": _modelo_saida(cfg["pasta_mp3"], cfg, playlist, modo="mp3"),
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": str(cfg.get("qualidade_mp3", "0")),
            },
            {"key": "FFmpegMetadata", "add_metadata": True},
        ],
        "writethumbnail": bool(cfg.get("escrever_thumbnail", True)),
    }
    if cfg.get("escrever_thumbnail", True):
        opts["postprocessors"].append({"key": "EmbedThumbnail", "already_have_thumbnail": False})
    return opts


def opcoes_mp4(cfg: dict, url: str, playlist: bool = False) -> dict:
    altura = int(cfg.get("altura_maxima_mp4", 1080) or 0)
    format_sort = ["res", "vbr", "abr", "quality"]
    if altura > 0:
        max_dim = int(altura * 16 / 9)  # 1920 para 1080p, 1280 para 720p
        fmt = f"bestvideo*[width<=?{max_dim}][height<=?{max_dim}]+bestaudio/bestvideo*+bestaudio/best"
    else:
        fmt = "bestvideo*+bestaudio/best"

    return {
        "format": fmt,
        "format_sort": format_sort,
        "merge_output_format": "mp4",
        "outtmpl": _modelo_saida(cfg["pasta_mp4"], cfg, playlist, modo="mp4"),
        "postprocessors": [{"key": "FFmpegMetadata", "add_metadata": True}],
        "writethumbnail": False,
    }


def opcoes_base(cfg: dict, url: str, verboso: bool = True, playlist: bool = False,
                modo: str = "mp3", contador: dict | None = None) -> dict:
    opts: dict = {
        "noplaylist": not playlist,
        # 'only_download': item ruim de playlist e pulado, MAS erro de extracao
        # continua estourando. Com True o yt-dlp devolvia None e a causa real
        # ("Sign in to confirm you're not a bot") sumia.
        "retries": 25,
        "fragment_retries": 25,
        "file_access_retries": 5,
        "continuedl": True,            # retoma download interrompido
        "concurrent_fragment_downloads": int(cfg.get("limite_downloads_simultaneos", 3)),
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "progress_hooks": [Progresso()],
        "restrictfilenames": False,
        "windowsfilenames": True,      # evita nomes invalidos no Windows
        "overwrites": False,
        "trim_file_name": 120,
        # sem isto o yt-dlp salva a CAPA DA PLAYLIST solta na pasta
        # (um "00 - Nome.jpg" orfao, sem audio para embutir)
        "allow_playlist_files": False,
    }
    if playlist:
        limite = int(cfg.get("limite_itens_playlist", 0) or 0)
        if limite > 0:
            opts["playlistend"] = limite

        # Respiro ALEATORIO entre uma musica e outra. Baixar 400 faixas em
        # rajada e o jeito mais rapido de tomar bloqueio; o intervalo variavel
        # imita uso humano e mantem a conta fora do radar.
        pmin = float(cfg.get("pausa_entre_musicas_min", 3) or 0)
        pmax = float(cfg.get("pausa_entre_musicas_max", 8) or 0)
        if pmax > 0:
            opts["sleep_interval"] = pmin
            opts["max_sleep_interval"] = max(pmax, pmin)
        # NOTA: aqui havia tambem o 'download_archive' do yt-dlp. Foi removido
        # porque criava DUAS fontes de verdade: quando o archive pulava um item,
        # o yt-dlp devolvia None sem passar pelo nosso filtro, e o programa nao
        # sabia distinguir "ja tinha" de "falhou" — reportava erro falso.
        # O historico SQLite sozinho faz o mesmo trabalho e sabe contar os pulos.

    if cfg.get("baixar_legendas"):
        opts.update(
            {
                "writesubtitles": True,
                "writeautomaticsub": True,
                "subtitleslangs": [cfg.get("idioma_legendas", "pt")],
            }
        )
    filtro = filtro_duplicadas(cfg, modo, contador if contador is not None else {})
    if filtro is not None:
        opts["match_filter"] = filtro

    opts.update(opcoes_de_login(url, cfg, verboso=verboso))
    return opts


def filtro_duplicadas(cfg: dict, modo: str, contador: dict):
    """Consulta o SQLite ANTES de baixar cada item e pula o que ja existe.

    O yt-dlp chama isso para cada entrada da playlist; devolver uma string faz
    ele pular aquele item. Contamos os pulos para nao confundir
    'tudo ja estava baixado' (sucesso) com 'nada pode ser baixado' (falha).
    """
    if not cfg.get("evitar_duplicadas", True):
        return None

    def filtro(info: dict, *, incomplete: bool = False):
        titulo = info.get("title") or ""
        if not titulo:
            return None
        tem, motivo = historico.ja_baixado(info.get("id"), titulo, modo=modo)
        if tem:
            contador["puladas"] = contador.get("puladas", 0) + 1
            if contador["puladas"] <= 8:
                print(f"    pulada: {titulo[:48]} — {motivo}")
            return f"ja baixado ({motivo})"
        return None

    return filtro


def anonimizar_video(caminho: Path, renomear: bool, limpar: bool) -> Path | None:
    """Deixa o MP4 sem rastro: nome UUID e zero metadados.

    Usa '-c copy', entao NAO recodifica: e uma remuxagem rapida, sem perda de
    qualidade. Remove tags do container, capitulos e a marca do encoder.
    """
    if not caminho.exists():
        return None

    novo_nome = f"{uuid.uuid4()}{caminho.suffix}" if renomear else caminho.name
    destino = caminho.with_name(novo_nome)

    if not limpar:
        if destino != caminho:
            caminho.rename(destino)
        return destino

    temporario = caminho.with_name(f"_limpando_{uuid.uuid4().hex[:8]}{caminho.suffix}")
    comando = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(caminho),
        "-map_metadata", "-1",     # tira titulo, artista, comentario, data...
        "-map_chapters", "-1",     # tira capitulos
        "-fflags", "+bitexact",    # tira a assinatura do encoder
        "-c", "copy",              # sem recodificar
        str(temporario),
    ]
    try:
        r = subprocess.run(comando, capture_output=True, text=True, timeout=600)
        if r.returncode != 0 or not temporario.exists():
            raise RuntimeError((r.stderr or "ffmpeg falhou")[:150])
        caminho.unlink(missing_ok=True)
        temporario.rename(destino)
        return destino
    except Exception as exc:  # noqa: BLE001
        temporario.unlink(missing_ok=True)
        print(f"    aviso: nao consegui limpar os metadados ({str(exc)[:70]})")
        if destino != caminho and caminho.exists():
            caminho.rename(destino)
            return destino
        return caminho


def _arquivos_de(info: dict) -> list[Path]:
    """Caminhos realmente gravados por um item ja baixado."""
    saida = []
    for req in info.get("requested_downloads") or []:
        caminho = req.get("filepath")
        if caminho:
            saida.append(Path(caminho))
    return saida


def pos_processar_videos(info: dict, cfg: dict) -> int:
    """Aplica nome aleatorio + limpeza de metadados nos MP4 baixados."""
    renomear = bool(cfg.get("nome_aleatorio_mp4", True))
    limpar = bool(cfg.get("remover_metadados_mp4", True))
    if not renomear and not limpar:
        return 0

    itens = []
    entradas = info.get("entries") if isinstance(info, dict) else None
    if entradas is not None:
        itens = [e for e in entradas if e]
    elif isinstance(info, dict):
        itens = [info]

    tratados = 0
    for it in itens:
        for caminho in _arquivos_de(it):
            novo = anonimizar_video(caminho, renomear, limpar)
            if novo:
                tratados += 1
                # o historico aponta para o arquivo novo
                it.setdefault("requested_downloads", [{}])[0]["filepath"] = str(novo)
    return tratados


def registrar_baixados(info: dict, modo: str, site: str) -> int:
    """Grava no historico o que realmente foi baixado agora."""
    itens = []
    entradas = info.get("entries") if isinstance(info, dict) else None
    if entradas is not None:
        itens = [e for e in entradas if e]
    elif isinstance(info, dict):
        itens = [info]

    novos = 0
    for it in itens:
        try:
            tem, _ = historico.ja_baixado(it.get("id"), it.get("title") or "", modo=modo)
            if tem:
                continue
            arquivo = ""
            req = it.get("requested_downloads") or []
            if req:
                arquivo = req[0].get("filepath") or ""
            historico.registrar(it, modo=modo, site=site, arquivo=arquivo)
            novos += 1
        except Exception:  # noqa: BLE001
            pass
    return novos


def contar_itens(url: str, cfg: dict) -> int:
    """Conta os itens da playlist sem baixar nada (extracao rasa, rapida)."""
    opts = {
        "extract_flat": True,
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
    }
    opts.update(opcoes_de_login(url, cfg, verboso=False))
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
        entradas = (info or {}).get("entries")
        return len(list(entradas)) if entradas else 0
    except Exception:  # noqa: BLE001
        return 0


def confirmar_playlist_grande(url: str, cfg: dict) -> int | None:
    """Nao interrompe: baixa a playlist automaticamente sem perguntar."""
    return None


def _executar(opts: dict, url: str):
    with YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=True)


def _erro_de_cookie(exc: Exception) -> bool:
    """Distingue 'nao consegui ler o login' de 'nao consegui baixar'."""
    m = str(exc).lower()
    return any(
        t in m
        for t in (
            "failed to load cookies",
            "could not find",
            "cookies database",
            "unable to decrypt",
            "could not copy",
            "permission denied",
            "database is locked",
        )
    )


def _registrar(linha: str) -> None:
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        with (LOGS_DIR / "downloads.log").open("a", encoding="utf-8") as fh:
            fh.write(f"{datetime.now().isoformat(timespec='seconds')} {linha}\n")
    except Exception:  # noqa: BLE001
        pass


def baixar(urls: list[str], modo: str, forcar_playlist: bool | None = None) -> int:
    """modo = 'mp3' ou 'mp4'. Devolve a quantidade de falhas."""
    cfg = carregar_config()
    garantir_pastas(cfg)

    destino = cfg["pasta_mp3"] if modo == "mp3" else cfg["pasta_mp4"]
    print(f"\n{'=' * 66}")
    print(f"  Baixando {len(urls)} item(ns) em {modo.upper()}")
    print(f"  Destino: {destino}")
    print(f"{'=' * 66}\n")

    falhas = 0
    for i, url in enumerate(urls, 1):
        site = site_da_url(url)
        print(f"[{i}/{len(urls)}] {url}")
        print(f"  site: {site}")

        playlist = deve_baixar_playlist(url, cfg, forcar_playlist)
        limite_escolhido = None
        if playlist:
            escolha = confirmar_playlist_grande(url, cfg)
            if escolha == -1:
                print("  cancelado por voce\n")
                continue
            limite_escolhido = escolha
            print("  playlist: baixando os itens")
            limite = limite_escolhido or int(cfg.get("limite_itens_playlist", 0) or 0)
            if limite:
                print(f"            (limitado aos {limite} primeiros)")

        contador = {"puladas": 0}
        opts = opcoes_base(cfg, url, playlist=playlist, modo=modo, contador=contador)
        if limite_escolhido:
            opts["playlistend"] = limite_escolhido
        opts.update(
            opcoes_mp3(cfg, url, playlist) if modo == "mp3" else opcoes_mp4(cfg, url, playlist)
        )

        try:
            try:
                info = _executar(opts, url)
            except Exception as exc:  # noqa: BLE001
                # Cookie quebrado nao pode impedir um video PUBLICO de baixar.
                # Sem isso, um Chrome travado derrubava a fila inteira.
                if not _erro_de_cookie(exc):
                    raise
                print(f"  aviso: nao consegui usar o login ({str(exc)[:70]})")
                print("         seguindo SEM login (funciona para conteudo publico)")
                sem_login = {k: v for k, v in opts.items() if k not in ("cookiesfrombrowser", "cookiefile")}
                info = _executar(sem_login, url)

            if info is None:
                raise DownloadError("sem informacoes (URL invalida ou bloqueada)")

            titulo = info.get("title") if isinstance(info, dict) else "?"

            # Numa playlist, 'ignoreerrors' pula item quebrado e devolve None
            # naquela posicao. Sem contar isso, uma playlist onde TUDO falhou
            # era reportada como sucesso.
            entradas = info.get("entries") if isinstance(info, dict) else None
            if entradas is not None:
                itens = list(entradas)
                bons = [e for e in itens if e]
                puladas = contador.get("puladas", 0)
                if not bons:
                    qtd = puladas or len(itens)
                    if qtd > 0:
                        print(f"  NADA NOVO: {qtd} musica(s) ja estavam no historico")
                        _registrar(f"DUP  {modo} {site} {url} :: {qtd} puladas")
                        print()
                        continue
                    raise DownloadError(
                        "nenhum item disponivel para baixar (playlist vazia ou bloqueada)"
                    )
                if modo == 'mp4':
                    pos_processar_videos(info, cfg)
                novos = registrar_baixados(info, modo, site)
                extra = f", {puladas} ja tinha(m)" if puladas else ""
                if len(bons) < len(itens):
                    print(f"  PARCIAL: {len(bons)} de {len(itens)} baixados{extra}")
                    _registrar(f"PARC {modo} {site} {url} :: {len(bons)}/{len(itens)}")
                else:
                    print(f"  OK: {titulo} ({len(bons)} baixados{extra})")
                    _registrar(f"OK   {modo} {site} {url} :: {len(bons)} itens")
                print()
                continue

            # Item unico pulado pelo historico: o yt-dlp devolve o info mesmo
            # sem baixar, entao sem olhar o contador isso virava um "OK" falso.
            if contador.get("puladas", 0):
                print(f"  JA TINHA: {titulo}\n")
                _registrar(f"DUP  {modo} {site} {url}")
                continue

            if modo == 'mp4':
                tratados = pos_processar_videos(info, cfg)
                if tratados:
                    print(f"  video anonimizado (nome UUID, sem metadados)")

            # item unico tambem precisa entrar no historico, senao baixar a
            # mesma musica de novo nunca seria detectado
            registrar_baixados(info, modo, site)
            print(f"  OK: {titulo}\n")
            _registrar(f"OK   {modo} {site} {url}")
        except DownloadError as exc:
            falhas += 1
            msg = str(exc)
            print(f"  FALHOU: {msg[:200]}")
            _registrar(f"ERRO {modo} {site} {url} :: {msg[:200]}")
            _explicar(msg, site)
            print()
        except Exception as exc:  # noqa: BLE001
            falhas += 1
            print(f"  FALHOU (inesperado): {exc}")
            _registrar(f"ERRO {modo} {site} {url} :: {exc}")
            print()

    ok = len(urls) - falhas
    print(f"{'=' * 66}")
    print(f"  Concluido: {ok} com sucesso, {falhas} com falha")
    print(f"  Arquivos em: {destino}")
    print(f"{'=' * 66}\n")
    return falhas


def _explicar(msg: str, site: str) -> None:
    """Traduz os erros mais comuns em acao pratica."""
    baixo = msg.lower()
    if "sign in" in baixo or "login" in baixo or "private" in baixo or "members-only" in baixo:
        print("  >> Precisa de login. Rode: CONFIGURAR-LOGIN.bat")
    elif "cookies" in baixo and ("database" in baixo or "locked" in baixo or "decrypt" in baixo):
        print("  >> O navegador travou o banco de cookies.")
        print("     Feche o navegador OU use o arquivo de cookies (CONFIGURAR-LOGIN.bat).")
    elif "age" in baixo and "restrict" in baixo:
        print("  >> Video com restricao de idade: precisa de login.")
    elif "unavailable" in baixo or "removed" in baixo:
        print("  >> Video removido ou indisponivel na sua regiao.")
    elif "ffmpeg" in baixo:
        print("  >> ffmpeg nao encontrado. Instale: winget install Gyan.FFmpeg")
    elif "429" in baixo or "too many" in baixo:
        print("  >> Muitas requisicoes. Espere alguns minutos.")
    elif site == "tiktok" and ("empty" in baixo or "unable to extract" in baixo):
        print("  >> TikTok muda o site com frequencia. Atualize: pip install -U yt-dlp")
