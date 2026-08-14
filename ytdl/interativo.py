#!/usr/bin/env python3
"""Modo interativo unificado por linha de comando com suporte a fila em segundo plano.

Permite colar URLs uma atras da outra no terminal. Cada URL entra imediatamente
na fila e o terminal libera a entrada NA HORA para colar a proxima, enquanto os
downloads acontecem em segundo plano, um por um.

Permite alternar o modo entre MP3 e MP4 a qualquer momento digitando 'mp3' ou 'mp4'.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from .comum import preparar_console, separar_opcoes
from .fila import BAIXANDO, ESPERANDO, Fila


def modo_interativo(modo_inicial: str = "mp3") -> int:
    preparar_console()
    modo_atual = modo_inicial.lower()

    print("\n" + "=" * 68)
    print("  BAIXADOR UNIFICADO - YOUTUBE / TIKTOK / INSTAGRAM / OUTROS")
    print("=" * 68)
    print("  - Paste a URL e aperte Enter. Ela entra na fila na hora!")
    print("  - O terminal libera a entrada imediatamente para a proxima URL.")
    print("  - Digite 'mp4' para mudar para modo VIDEO MP4.")
    print("  - Digite 'mp3' para mudar para modo AUDIO MP3.")
    print("  - Para encerrar: digite 'sair' ou aperte Enter em linha vazia.")
    print("=" * 68 + "\n")

    def ao_log(linha: str):
        if linha.strip():
            print(f"    {linha}", flush=True)

    fila = Fila(ao_log=ao_log)
    fila.iniciar()

    try:
        while True:
            rotulo = "AUDIO MP3" if modo_atual == "mp3" else "VIDEO MP4"
            try:
                entrada = input(f"  [{rotulo}] Cole a URL: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if not entrada or entrada.lower() in ("sair", "exit", "q"):
                break

            baixo = entrada.lower()
            if baixo in ("mp3", "audio"):
                modo_atual = "mp3"
                print("  [!] Modo alterado para AUDIO MP3\n")
                continue
            if baixo in ("mp4", "video"):
                modo_atual = "mp4"
                print("  [!] Modo alterado para VIDEO MP4\n")
                continue

            urls, forcado_opc = separar_opcoes(entrada.split())
            if not urls:
                print("  [!] Nenhuma URL reconhecida. Tente novamente.\n")
                continue

            modo_forcar = "auto"
            if forcado_opc is True:
                modo_forcar = "playlist"
            elif forcado_opc is False:
                modo_forcar = "so-um"

            for url in urls:
                item = fila.adicionar(url, modo_atual, modo_forcar)
                if item:
                    print(f"  [+] Adicionado a fila #{item.id} ({item.modo.upper()}): {url}")
                else:
                    print(f"  [!] Ja esta na fila ou link invalido: {url}")
            print()
    finally:
        pendentes = [i for i in fila.itens if i.estado in (ESPERANDO, BAIXANDO)]
        if pendentes:
            print(f"\n  Aguardando {len(pendentes)} item(ns) na fila terminarem...")
            print("  (Pressione Ctrl+C para encerrar imediatamente)\n")
            try:
                while any(i.estado in (ESPERANDO, BAIXANDO) for i in fila.itens):
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n  Encerrando...")
                fila.parar_agora()

    return 0
