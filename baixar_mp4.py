#!/usr/bin/env python3
"""Baixa video em MP4 (YouTube, YouTube Music, TikTok, etc).

Uso:
  baixar_mp4.py <url> [<url>...]     detecta playlist sozinho pelo link
  baixar_mp4.py --playlist <url>     forca baixar a playlist inteira
  baixar_mp4.py --so-um <url>        forca baixar so aquele item
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ytdl.baixar import baixar
from ytdl.comum import preparar_console, separar_opcoes
from ytdl.interativo import modo_interativo


def main() -> int:
    preparar_console()
    urls, forcado = separar_opcoes(sys.argv[1:])
    if not urls:
        return modo_interativo("mp4")
    return 1 if baixar(urls, "mp4", forcar_playlist=forcado) else 0


if __name__ == "__main__":
    raise SystemExit(main())
