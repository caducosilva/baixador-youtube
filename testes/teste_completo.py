#!/usr/bin/env python3
"""Bateria de testes controlados do projeto.

Cobre o que importa na pratica:
  1. mesma musica pedida varias vezes -> so baixa uma
  2. musicas diferentes -> todas baixam
  3. playlist -> baixa varias e organiza
  4. fila com MP3 e MP4 misturados -> nao se confunde
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from ytdl.comum import carregar_config  # noqa: E402
from ytdl.historico import BANCO, conectar, estatisticas  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

# musicas curtas e estaveis para teste
M1 = "https://www.youtube.com/watch?v=eT6dLJd3rYk"   # AURORA - I Went Too Far
M1_ALT = "https://youtu.be/eT6dLJd3rYk"              # mesma musica, outra forma de link
M2 = "https://www.youtube.com/watch?v=QUDiLmbWlOs"   # Temperance
PLAYLIST = "https://www.youtube.com/playlist?list=PLa1F2ddGya_8u-HEvmfCVuS_OImW8HaLd"

resultados: list[tuple[str, bool, str]] = []


def registrar(nome: str, ok: bool, detalhe: str = "") -> None:
    resultados.append((nome, ok, detalhe))
    marca = "PASSOU" if ok else "FALHOU"
    print(f"  [{marca}] {nome}" + (f" — {detalhe}" if detalhe else ""))


def rodar(script: str, *args: str, timeout: int = 420) -> tuple[int, str]:
    cmd = [sys.executable, str(RAIZ / script), *args]
    p = subprocess.run(
        cmd, cwd=str(RAIZ), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=timeout,
        stdin=subprocess.DEVNULL,
    )
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def total_banco() -> int:
    return estatisticas()["total"]


def limpar_banco() -> None:
    if BANCO.exists():
        conn = conectar()
        conn.execute("DELETE FROM baixados")
        conn.commit()
        conn.close()
    arq = RAIZ / "logs" / "ja_baixados.txt"
    arq.unlink(missing_ok=True)


def teste_1_mesma_musica() -> None:
    print("\n--- 1. MESMA MUSICA VARIAS VEZES ---")
    limpar_banco()
    antes = total_banco()

    cod, saida = rodar("baixar_mp3.py", "--so-um", M1)
    ok1 = cod == 0 and total_banco() == antes + 1
    registrar("1a vez baixa", ok1, f"banco: {antes} -> {total_banco()}")

    marca = total_banco()
    cod, saida = rodar("baixar_mp3.py", "--so-um", M1)
    pulou = any(t in saida.lower() for t in ("ja baixad", "nada novo", "ja tinha"))
    registrar("2a vez pula (mesma URL)", total_banco() == marca and pulou,
              f"banco continua {total_banco()}")

    cod, saida = rodar("baixar_mp3.py", "--so-um", M1_ALT)
    pulou2 = any(t in saida.lower() for t in ("ja baixad", "nada novo", "ja tinha"))
    registrar("3a vez pula (URL curta youtu.be)", total_banco() == marca and pulou2,
              f"banco continua {total_banco()}")


def teste_2_musicas_diferentes() -> None:
    print("\n--- 2. MUSICA DIFERENTE AINDA BAIXA ---")
    antes = total_banco()
    cod, saida = rodar("baixar_mp3.py", "--so-um", M2)
    registrar("musica nova baixa normalmente", cod == 0 and total_banco() == antes + 1,
              f"banco: {antes} -> {total_banco()}")


def teste_3_playlist() -> None:
    print("\n--- 3. PLAYLIST ---")
    cfg_path = RAIZ / "config.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    original = cfg.get("limite_itens_playlist", 0)
    cfg["limite_itens_playlist"] = 3
    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        antes = total_banco()
        cod, saida = rodar("baixar_mp3.py", "--playlist", PLAYLIST, timeout=600)
        depois = total_banco()
        registrar("playlist baixa varios itens", cod == 0 and depois > antes,
                  f"banco: {antes} -> {depois}")

        pasta = Path(carregar_config()["pasta_mp3"])
        subpastas = [p for p in pasta.iterdir() if p.is_dir()] if pasta.exists() else []
        registrar("criou subpasta da playlist", len(subpastas) > 0,
                  f"{len(subpastas)} subpasta(s)")

        marca = total_banco()
        cod, saida = rodar("baixar_mp3.py", "--playlist", PLAYLIST, timeout=600)
        registrar("2a vez na playlist nao rebaixa",
                  total_banco() == marca and ("nada novo" in saida.lower() or "ja tinha" in saida.lower()),
                  f"banco continua {marca}")
    finally:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        cfg["limite_itens_playlist"] = original
        cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def teste_4_fila_mista() -> None:
    print("\n--- 4. FILA COM MP3 E MP4 MISTURADOS ---")
    from ytdl.fila import CONCLUIDO, ESPERANDO, FILA_PATH, Fila

    FILA_PATH.unlink(missing_ok=True)
    fila = Fila()
    fila.pausa_entre_itens = 2

    a = fila.adicionar(M1, "mp3", "so-um")     # ja no banco -> deve pular rapido
    b = fila.adicionar(M2, "mp4", "so-um")     # video novo
    c = fila.adicionar(M1, "mp4", "so-um")     # mesma musica, mas em VIDEO
    registrar("aceitou 3 itens misturados", None not in (a, b, c),
              f"modos: {[i.modo for i in fila.itens]}")

    d = fila.adicionar(M2, "mp4", "so-um")
    registrar("rejeitou duplicado na fila (mesma url + mesmo modo)", d is None)

    fila.iniciar()
    limite = time.time() + 600
    while time.time() < limite:
        if all(i.estado not in (ESPERANDO, "baixando") for i in fila.itens):
            break
        time.sleep(3)
    fila.parar_agora()

    estados = [(i.modo, i.estado) for i in fila.itens]
    todos_ok = all(e == CONCLUIDO for _m, e in estados)
    registrar("fila processou tudo sem se confundir", todos_ok, str(estados))

    pasta_mp4 = Path(carregar_config()["pasta_mp4"])
    mp4s = list(pasta_mp4.glob("*.mp4")) if pasta_mp4.exists() else []
    registrar("gerou arquivos MP4 de verdade", len(mp4s) > 0, f"{len(mp4s)} arquivo(s) .mp4")


def main() -> int:
    print("=" * 68)
    print("  BATERIA DE TESTES")
    print("=" * 68)
    inicio = time.time()

    teste_1_mesma_musica()
    teste_2_musicas_diferentes()
    teste_3_playlist()
    teste_4_fila_mista()

    print("\n" + "=" * 68)
    passou = sum(1 for _n, ok, _d in resultados if ok)
    total = len(resultados)
    print(f"  RESULTADO: {passou}/{total} testes passaram  ({time.time() - inicio:.0f}s)")
    if passou < total:
        print("\n  falharam:")
        for n, ok, d in resultados:
            if not ok:
                print(f"    - {n}: {d}")
    print("=" * 68)
    return 0 if passou == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
