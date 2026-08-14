#!/usr/bin/env python3
"""Baixador Unificado (MP3 / MP4).

Uso:
  baixar.py                          abre a fila interativa no terminal
  baixar.py <url> [<url>...]         baixa como MP3 (padrao)
  baixar.py --mp4 <url> [<url>...]   baixa como MP4
  baixar.py --mp3 <url> [<url>...]   baixa como MP3
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
    argv = list(sys.argv[1:])

    modo = "mp3"
    if "--mp4" in argv:
        modo = "mp4"
        argv.remove("--mp4")
    elif "--mp3" in argv:
        modo = "mp3"
        argv.remove("--mp3")

    urls, forcado = separar_opcoes(argv)
    if not urls:
        return modo_interativo(modo)
    return 1 if baixar(urls, modo, forcar_playlist=forcado) else 0


if __name__ == "__main__":
    raise SystemExit(main())
