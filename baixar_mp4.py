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


def main() -> int:
    preparar_console()
    urls, forcado = separar_opcoes(sys.argv[1:])
    if not urls:
        print("\n  BAIXAR VIDEO EM MP4")
        print("  Cole a(s) URL(s) e de Enter. Varias? separe por espaco.")
        print("  Playlist e detectada sozinha. Para mandar voce mesmo,")
        print("  escreva --playlist ou --so-um junto da URL.\n")
        entrada = input("  URL: ").strip()
        urls, extra = separar_opcoes(entrada.split())
        if extra is not None:
            forcado = extra
    if not urls:
        print("Nenhuma URL informada.")
        return 1
    return 1 if baixar(urls, "mp4", forcar_playlist=forcado) else 0


if __name__ == "__main__":
    raise SystemExit(main())
