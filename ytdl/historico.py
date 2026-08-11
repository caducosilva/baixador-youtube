#!/usr/bin/env python3
"""Historico em SQLite das musicas ja baixadas (evita duplicata).

Por que SQLite e nao so o arquivo do yt-dlp: o 'download_archive' do yt-dlp
guarda apenas o ID do video. A MESMA musica aparece com IDs diferentes (clipe
oficial, audio oficial, versao no YouTube Music, dentro de um mix...). Aqui a
gente guarda tambem o TITULO normalizado, entao a musica repetida e pulada
mesmo vindo de outro link.
"""

from __future__ import annotations

import re
import sqlite3
import unicodedata
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BANCO = RAIZ / "historico.db"

# ruido comum em titulo do YouTube que atrapalha a comparacao
_LIXO = re.compile(
    r"\b(official\s*(music\s*)?(video|audio|lyric\s*video)?|video\s*oficial|audio\s*oficial|"
    r"lyrics?|letra|legendado|hd|hq|4k|full\s*hd|remaster(ed)?(\s*\d{4})?|"
    r"ao\s*vivo|live|clipe\s*oficial|visualizer|m/?v)\b",
    re.I,
)


def conectar() -> sqlite3.Connection:
    conn = sqlite3.connect(str(BANCO), timeout=15)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS baixados (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id      TEXT,
            titulo        TEXT NOT NULL,
            titulo_norm   TEXT NOT NULL,
            artista       TEXT,
            site          TEXT,
            modo          TEXT,
            url           TEXT,
            arquivo       TEXT,
            duracao       INTEGER,
            baixado_em    TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_video_id ON baixados(video_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_titulo_norm ON baixados(titulo_norm)")
    conn.commit()
    return conn


def normalizar(texto: str) -> str:
    """Reduz o titulo a uma forma comparavel.

    'AURORA - Runaway (Official Video) [HD]'  ->  'aurora runaway'
    """
    if not texto:
        return ""
    t = unicodedata.normalize("NFKD", texto)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.lower()
    t = re.sub(r"[\(\[\{].*?[\)\]\}]", " ", t)   # tira (...) [...] {...}
    t = _LIXO.sub(" ", t)
    t = re.sub(r"[^a-z0-9]+", " ", t)
    t = re.sub(r"\b(feat|ft|com)\b", " ", t)
    return " ".join(t.split())


def ja_baixado(video_id: str | None, titulo: str, artista: str = "", modo: str = "") -> tuple[bool, str]:
    """(ja_tem, motivo). Confere pelo ID e depois pelo titulo.

    O modo entra na conta: a MESMA musica em mp3 e em mp4 sao entregas
    diferentes, entao pedir o video depois de ja ter o audio deve funcionar.
    """
    norm = normalizar(titulo)
    if not norm and not video_id:
        return False, ""
    conn = conectar()
    try:
        filtro_modo = " AND modo = ?" if modo else ""
        extra = (modo,) if modo else ()
        if video_id:
            linha = conn.execute(
                f"SELECT titulo, baixado_em FROM baixados WHERE video_id = ?{filtro_modo} LIMIT 1",
                (video_id, *extra),
            ).fetchone()
            if linha:
                return True, f"mesmo video, baixado em {linha[1][:10]}"
        if norm:
            linha = conn.execute(
                f"SELECT titulo, baixado_em FROM baixados WHERE titulo_norm = ?{filtro_modo} LIMIT 1",
                (norm, *extra),
            ).fetchone()
            if linha:
                return True, f"mesma musica '{linha[0][:40]}' ({linha[1][:10]})"
        return False, ""
    finally:
        conn.close()


def registrar(info: dict, modo: str, site: str = "", arquivo: str = "") -> None:
    titulo = (info.get("title") or "").strip()
    if not titulo:
        return
    artista = (info.get("artist") or info.get("uploader") or "").strip()
    conn = conectar()
    try:
        conn.execute(
            """INSERT INTO baixados
               (video_id, titulo, titulo_norm, artista, site, modo, url, arquivo, duracao, baixado_em)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                info.get("id"),
                titulo,
                normalizar(titulo),
                artista,
                site,
                modo,
                info.get("webpage_url") or info.get("original_url"),
                arquivo or (info.get("filepath") or ""),
                int(info.get("duration") or 0),
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def estatisticas() -> dict:
    conn = conectar()
    try:
        total = conn.execute("SELECT COUNT(*) FROM baixados").fetchone()[0]
        por_modo = dict(conn.execute("SELECT modo, COUNT(*) FROM baixados GROUP BY modo").fetchall())
        por_site = dict(conn.execute("SELECT site, COUNT(*) FROM baixados GROUP BY site").fetchall())
        ultimos = conn.execute(
            "SELECT titulo, modo, baixado_em FROM baixados ORDER BY id DESC LIMIT 5"
        ).fetchall()
        return {"total": total, "por_modo": por_modo, "por_site": por_site, "ultimos": ultimos}
    finally:
        conn.close()
