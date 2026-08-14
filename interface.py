#!/usr/bin/env python3
"""Interface grafica responsiva em PySide6 para o Baixador de Videos e Musicas."""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

from app import main

if __name__ == "__main__":
    main()
