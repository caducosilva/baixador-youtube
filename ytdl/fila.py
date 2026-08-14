#!/usr/bin/env python3
"""Fila de downloads: um item por vez, na ordem em que voce adicionou.

Roda cada item como PROCESSO SEPARADO (baixar_mp3.py / baixar_mp4.py). Isso:
  * garante 1 download por vez de verdade (nada em paralelo);
  * isola falhas (um item quebrado nao derruba a fila);
  * reaproveita todo o motor ja testado, sem duplicar codigo.

A fila e salva em disco, entao fechar o programa nao perde o que esta na lista.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
FILA_PATH = RAIZ / "fila.json"

ESPERANDO = "esperando"
BAIXANDO = "baixando"
CONCLUIDO = "concluido"
FALHOU = "falhou"
CANCELADO = "cancelado"


@dataclass
class Item:
    url: str
    modo: str = "mp3"                 # mp3 | mp4
    forcar: str = "auto"              # auto | playlist | so-um
    estado: str = ESPERANDO
    titulo: str = ""
    detalhe: str = ""
    progresso: str = ""
    adicionado_em: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    id: int = 0


class Fila:
    def __init__(self, ao_mudar=None, ao_log=None) -> None:
        self.itens: list[Item] = []
        self._lock = threading.Lock()
        self._rodando = False
        self._pausado = False
        self._proc: subprocess.Popen | None = None
        self._thread: threading.Thread | None = None
        self._proximo_id = 1
        self.ao_mudar = ao_mudar or (lambda: None)
        self.ao_log = ao_log or (lambda linha: None)
        self.pausa_entre_itens = 5     # segundos, para nao martelar o site
        self.carregar()

    # ------------------------------------------------------------ persistencia
    def carregar(self) -> None:
        if not FILA_PATH.exists():
            return
        try:
            dados = json.loads(FILA_PATH.read_text(encoding="utf-8"))
            self.itens = [Item(**d) for d in dados.get("itens", [])]
            self._proximo_id = max((i.id for i in self.itens), default=0) + 1
            # item que ficou "baixando" de uma sessao anterior volta para a fila
            for it in self.itens:
                if it.estado == BAIXANDO:
                    it.estado = ESPERANDO
                    it.detalhe = "retomado apos fechar o programa"
        except Exception:  # noqa: BLE001
            self.itens = []

    def salvar(self) -> None:
        try:
            FILA_PATH.write_text(
                json.dumps({"itens": [asdict(i) for i in self.itens]}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------------ fila
    def adicionar(self, url: str, modo: str, forcar: str = "auto") -> Item | None:
        url = (url or "").strip()
        if not url or not url.lower().startswith(("http://", "https://")):
            return None
        with self._lock:
            # nao repete o que ja esta esperando com o mesmo modo
            for it in self.itens:
                if it.url == url and it.modo == modo and it.estado in (ESPERANDO, BAIXANDO):
                    return None
            item = Item(url=url, modo=modo, forcar=forcar, id=self._proximo_id)
            self._proximo_id += 1
            self.itens.append(item)
        self.salvar()
        self.ao_mudar()
        return item

    def remover(self, item_id: int) -> None:
        with self._lock:
            alvo = next((i for i in self.itens if i.id == item_id), None)
            if alvo is None:
                return
            if alvo.estado == BAIXANDO:
                alvo.estado = CANCELADO
                self._matar_processo()
            else:
                self.itens.remove(alvo)
        self.salvar()
        self.ao_mudar()

    def retentar_falhas(self) -> int:
        count = 0
        with self._lock:
            for i in self.itens:
                if i.estado in (FALHOU, CANCELADO):
                    i.estado = ESPERANDO
                    i.detalhe = "re-tentando download..."
                    count += 1
        if count > 0:
            self.salvar()
            self.ao_mudar()
        return count

    def limpar_terminados(self) -> None:
        with self._lock:
            self.itens = [i for i in self.itens if i.estado in (ESPERANDO, BAIXANDO)]
        self.salvar()
        self.ao_mudar()

    def subir(self, item_id: int) -> None:
        with self._lock:
            idx = next((n for n, i in enumerate(self.itens) if i.id == item_id), None)
            if idx is None or idx == 0:
                return
            if self.itens[idx].estado != ESPERANDO:
                return
            self.itens[idx - 1], self.itens[idx] = self.itens[idx], self.itens[idx - 1]
        self.salvar()
        self.ao_mudar()

    def _proximo(self) -> Item | None:
        with self._lock:
            return next((i for i in self.itens if i.estado == ESPERANDO), None)

    # --------------------------------------------------------------- execucao
    def iniciar(self) -> None:
        if self._rodando:
            self._pausado = False
            return
        self._rodando = True
        self._pausado = False
        self._thread = threading.Thread(target=self._loop, daemon=True, name="fila")
        self._thread.start()

    def pausar(self) -> None:
        """Pausa DEPOIS do item atual terminar (nao corta no meio)."""
        self._pausado = True
        self.ao_mudar()

    @property
    def pausado(self) -> bool:
        return self._pausado

    @property
    def rodando(self) -> bool:
        return self._rodando

    def parar_agora(self) -> None:
        self._pausado = True
        self._matar_processo()

    def _matar_processo(self) -> None:
        proc = self._proc
        if proc and proc.poll() is None:
            try:
                proc.kill()
            except Exception:  # noqa: BLE001
                pass

    def _python(self) -> str:
        return sys.executable

    def _comando(self, item: Item) -> list[str]:
        script = "baixar_mp3.py" if item.modo == "mp3" else "baixar_mp4.py"
        cmd = [self._python(), str(RAIZ / script)]
        if item.forcar == "playlist":
            cmd.append("--playlist")
        elif item.forcar == "so-um":
            cmd.append("--so-um")
        cmd.append(item.url)
        return cmd

    def _loop(self) -> None:
        while self._rodando:
            if self._pausado:
                time.sleep(0.5)
                continue

            item = self._proximo()
            if item is None:
                time.sleep(0.8)
                continue

            item.estado = BAIXANDO
            item.detalhe = "iniciando..."
            self.salvar()
            self.ao_mudar()
            self.ao_log(f"=== [{item.modo.upper()}] {item.url}")

            try:
                self._proc = subprocess.Popen(
                    self._comando(item),
                    cwd=str(RAIZ),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                    stdin=subprocess.DEVNULL,   # nunca trava esperando resposta
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                assert self._proc.stdout is not None
                for linha in self._proc.stdout:
                    linha = linha.rstrip()
                    if not linha:
                        continue
                    self.ao_log(linha)
                    self._interpretar(item, linha)
                codigo = self._proc.wait()
            except Exception as exc:  # noqa: BLE001
                item.estado = FALHOU
                item.detalhe = str(exc)[:120]
                self.ao_log(f"ERRO: {exc}")
                codigo = 1
            finally:
                self._proc = None

            if self._pausado or not self._rodando:
                item.estado = ESPERANDO
                item.detalhe = "interrompido; aguardando retomada"
            elif item.estado == CANCELADO:
                self.ao_log("cancelado por voce")
            elif codigo == 0:
                item.estado = CONCLUIDO
                if not item.detalhe or item.detalhe == "iniciando...":
                    item.detalhe = "pronto"
            else:
                item.estado = FALHOU
                if not item.detalhe or item.detalhe == "iniciando...":
                    item.detalhe = "falhou (veja o log)"

            self.salvar()
            self.ao_mudar()

            # respiro entre itens: evita parecer robo e tomar bloqueio
            if self._proximo() is not None and not self._pausado:
                for _ in range(int(self.pausa_entre_itens * 2)):
                    if self._pausado or not self._rodando:
                        break
                    time.sleep(0.5)

    def _interpretar(self, item: Item, linha: str) -> None:
        """Extrai titulo e progresso das linhas do downloader."""
        if linha.startswith("  OK: "):
            item.titulo = linha[6:].strip()[:70]
            item.detalhe = "pronto"
        elif "PARCIAL:" in linha:
            item.detalhe = linha.split("PARCIAL:")[-1].strip()[:70]
        elif "NADA NOVO:" in linha:
            item.detalhe = "ja estava tudo baixado"
        elif linha.strip().startswith("pulada:"):
            item.detalhe = "pulando repetidas..."
        elif "%" in linha and ("MB" in linha or "KB" in linha or "GB" in linha):
            item.detalhe = linha.strip()[:64]
            m = re.search(r"\[(\d+)/(\d+)\]", linha)
            if m:
                item.progresso = f"{m.group(1)}/{m.group(2)}"
        elif "baixado; convertendo" in linha:
            m = re.search(r"\[(\d+)/(\d+)\]", linha)
            if m:
                item.progresso = f"{m.group(1)}/{m.group(2)}"
            item.detalhe = "convertendo para o formato final..."
        elif "playlist:" in linha:
            item.detalhe = "lendo playlist..."
        elif "login:" in linha:
            item.detalhe = "autenticando..."
        elif linha.startswith("  FALHOU"):
            item.detalhe = linha.replace("FALHOU:", "").strip()[:70]
        self.ao_mudar()
