#!/usr/bin/env python3
"""Interface minimalista: cola o link, entra na fila, baixa um por vez.

Tkinter de proposito: ja vem com o Python, abre instantaneo e nao precisa
instalar nada. A janela so faz o essencial - adicionar URL, ver a fila andar
e acompanhar o log.
"""

from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import font as tkfont
from tkinter import ttk

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ytdl.fila import BAIXANDO, CANCELADO, CONCLUIDO, ESPERANDO, FALHOU, Fila  # noqa: E402

# paleta escura simples
FUNDO = "#15161a"
PAINEL = "#1d1f26"
BORDA = "#2c2f3a"
TEXTO = "#e6e7ea"
FRACO = "#8b8f9e"
AZUL = "#4f7cff"
VERDE = "#2ea86a"
AMARELO = "#d99b28"
VERMELHO = "#d9534f"

CORES_ESTADO = {
    ESPERANDO: FRACO,
    BAIXANDO: AMARELO,
    CONCLUIDO: VERDE,
    FALHOU: VERMELHO,
    CANCELADO: FRACO,
}
ROTULO_ESTADO = {
    ESPERANDO: "na fila",
    BAIXANDO: "baixando",
    CONCLUIDO: "pronto",
    FALHOU: "falhou",
    CANCELADO: "cancelado",
}


class App:
    def __init__(self, raiz: tk.Tk) -> None:
        self.raiz = raiz
        raiz.title("Baixador YouTube / YouTube Music")
        raiz.geometry("860x620")
        raiz.minsize(700, 480)
        raiz.configure(bg=FUNDO)

        self.mono = tkfont.Font(family="Consolas", size=9)
        self.fonte = tkfont.Font(family="Segoe UI", size=10)
        self.fonte_b = tkfont.Font(family="Segoe UI", size=10, weight="bold")

        self.fila = Fila(ao_mudar=self._agendar_redesenho, ao_log=self._agendar_log)
        self._pendente_log: list[str] = []
        self._redesenho_agendado = False

        self._montar()
        self._redesenhar()
        self.fila.iniciar()
        raiz.protocol("WM_DELETE_WINDOW", self._fechar)

    # ------------------------------------------------------------------ layout
    def _montar(self) -> None:
        topo = tk.Frame(self.raiz, bg=FUNDO)
        topo.pack(fill="x", padx=14, pady=(14, 8))

        tk.Label(
            topo, text="Cole o link do YouTube ou YouTube Music",
            bg=FUNDO, fg=FRACO, font=self.fonte, anchor="w",
        ).pack(fill="x")

        linha = tk.Frame(topo, bg=FUNDO)
        linha.pack(fill="x", pady=(6, 0))

        self.entrada = tk.Entry(
            linha, bg=PAINEL, fg=TEXTO, insertbackground=TEXTO,
            relief="flat", font=self.fonte, highlightthickness=1,
            highlightbackground=BORDA, highlightcolor=AZUL,
        )
        self.entrada.pack(side="left", fill="x", expand=True, ipady=7, padx=(0, 8))
        self.entrada.bind("<Return>", lambda _e: self._adicionar())

        self.modo = tk.StringVar(value="mp3")
        for texto, valor in (("MP3", "mp3"), ("MP4", "mp4")):
            tk.Radiobutton(
                linha, text=texto, variable=self.modo, value=valor,
                bg=FUNDO, fg=TEXTO, selectcolor=PAINEL, activebackground=FUNDO,
                activeforeground=TEXTO, font=self.fonte_b, relief="flat", bd=0,
                highlightthickness=0,
            ).pack(side="left", padx=(0, 6))

        self.botao_add = tk.Button(
            linha, text="+ Adicionar", command=self._adicionar,
            bg=AZUL, fg="white", font=self.fonte_b, relief="flat",
            activebackground="#3d63d6", activeforeground="white",
            padx=16, pady=6, cursor="hand2", bd=0,
        )
        self.botao_add.pack(side="left")

        self.forcar = tk.StringVar(value="auto")
        opc = tk.Frame(topo, bg=FUNDO)
        opc.pack(fill="x", pady=(6, 0))
        for texto, valor in (
            ("detectar sozinho", "auto"),
            ("forcar playlist inteira", "playlist"),
            ("so este item", "so-um"),
        ):
            tk.Radiobutton(
                opc, text=texto, variable=self.forcar, value=valor,
                bg=FUNDO, fg=FRACO, selectcolor=PAINEL, activebackground=FUNDO,
                activeforeground=TEXTO, font=self.fonte, relief="flat", bd=0,
                highlightthickness=0,
            ).pack(side="left", padx=(0, 12))

        # ---- fila
        cabec = tk.Frame(self.raiz, bg=FUNDO)
        cabec.pack(fill="x", padx=14, pady=(10, 4))
        self.lbl_fila = tk.Label(
            cabec, text="FILA", bg=FUNDO, fg=FRACO, font=self.fonte_b, anchor="w"
        )
        self.lbl_fila.pack(side="left")

        self.btn_pausar = tk.Button(
            cabec, text="Pausar", command=self._alternar_pausa,
            bg=PAINEL, fg=TEXTO, font=self.fonte, relief="flat",
            activebackground=BORDA, padx=12, pady=3, cursor="hand2", bd=0,
        )
        self.btn_pausar.pack(side="right", padx=(6, 0))
        tk.Button(
            cabec, text="Limpar prontos", command=self.fila.limpar_terminados,
            bg=PAINEL, fg=FRACO, font=self.fonte, relief="flat",
            activebackground=BORDA, padx=12, pady=3, cursor="hand2", bd=0,
        ).pack(side="right")

        quadro = tk.Frame(self.raiz, bg=PAINEL, highlightthickness=1, highlightbackground=BORDA)
        quadro.pack(fill="both", expand=True, padx=14)

        self.canvas = tk.Canvas(quadro, bg=PAINEL, highlightthickness=0)
        barra = ttk.Scrollbar(quadro, orient="vertical", command=self.canvas.yview)
        self.lista = tk.Frame(self.canvas, bg=PAINEL)
        self.lista.bind(
            "<Configure>", lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.janela_lista = self.canvas.create_window((0, 0), window=self.lista, anchor="nw")
        self.canvas.bind(
            "<Configure>", lambda e: self.canvas.itemconfig(self.janela_lista, width=e.width)
        )
        self.canvas.configure(yscrollcommand=barra.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")
        self.canvas.bind_all("<MouseWheel>", self._rolar)

        # ---- log
        tk.Label(
            self.raiz, text="LOG", bg=FUNDO, fg=FRACO, font=self.fonte_b, anchor="w"
        ).pack(fill="x", padx=14, pady=(10, 4))

        caixa = tk.Frame(self.raiz, bg=PAINEL, highlightthickness=1, highlightbackground=BORDA)
        caixa.pack(fill="x", padx=14, pady=(0, 14))
        self.log = tk.Text(
            caixa, height=8, bg=PAINEL, fg=FRACO, font=self.mono,
            relief="flat", wrap="none", state="disabled",
        )
        self.log.pack(fill="both", expand=True, padx=6, pady=6)

    def _rolar(self, evento) -> None:
        try:
            self.canvas.yview_scroll(int(-1 * (evento.delta / 120)), "units")
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------------ acoes
    def _adicionar(self) -> None:
        texto = self.entrada.get().strip()
        if not texto:
            return
        adicionados = 0
        # aceita varios links colados de uma vez (espaco ou quebra de linha)
        for url in texto.replace("\n", " ").split():
            if self.fila.adicionar(url, self.modo.get(), self.forcar.get()):
                adicionados += 1
        if adicionados:
            self.entrada.delete(0, "end")
            self._agendar_log(f"+ {adicionados} link(s) na fila")
        else:
            self._agendar_log("! link invalido ou ja esta na fila")

    def _alternar_pausa(self) -> None:
        if self.fila.pausado:
            self.fila.iniciar()
        else:
            self.fila.pausar()
        self._redesenhar()

    def _fechar(self) -> None:
        self.fila.parar_agora()
        self.raiz.destroy()

    # --------------------------------------------------------------- desenho
    def _agendar_redesenho(self) -> None:
        if self._redesenho_agendado:
            return
        self._redesenho_agendado = True
        self.raiz.after(120, self._redesenhar)

    def _agendar_log(self, linha: str) -> None:
        self._pendente_log.append(linha)
        self.raiz.after(60, self._escoar_log)

    def _escoar_log(self) -> None:
        if not self._pendente_log:
            return
        linhas, self._pendente_log = self._pendente_log, []
        self.log.configure(state="normal")
        for l in linhas:
            self.log.insert("end", l + "\n")
        # segura o tamanho do log
        if int(self.log.index("end-1c").split(".")[0]) > 400:
            self.log.delete("1.0", "200.0")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _redesenhar(self) -> None:
        self._redesenho_agendado = False
        for w in self.lista.winfo_children():
            w.destroy()

        itens = list(self.fila.itens)
        esperando = sum(1 for i in itens if i.estado == ESPERANDO)
        self.lbl_fila.configure(text=f"FILA — {esperando} esperando, {len(itens)} no total")
        self.btn_pausar.configure(text="Retomar" if self.fila.pausado else "Pausar")

        if not itens:
            tk.Label(
                self.lista, text="\nNada na fila.\nCole um link acima e clique em Adicionar.\n",
                bg=PAINEL, fg=FRACO, font=self.fonte, justify="center",
            ).pack(fill="x", pady=20)
            return

        for item in itens:
            self._linha_item(item)

    def _linha_item(self, item) -> None:
        cor = CORES_ESTADO.get(item.estado, FRACO)
        linha = tk.Frame(self.lista, bg=PAINEL)
        linha.pack(fill="x", padx=8, pady=3)

        marca = tk.Frame(linha, bg=cor, width=3)
        marca.pack(side="left", fill="y", padx=(0, 8))

        meio = tk.Frame(linha, bg=PAINEL)
        meio.pack(side="left", fill="x", expand=True)

        cabec = tk.Frame(meio, bg=PAINEL)
        cabec.pack(fill="x")
        tk.Label(
            cabec, text=item.modo.upper(), bg=BORDA, fg=TEXTO,
            font=self.mono, padx=5,
        ).pack(side="left", padx=(0, 6))
        tk.Label(
            cabec, text=ROTULO_ESTADO.get(item.estado, item.estado),
            bg=PAINEL, fg=cor, font=self.fonte_b,
        ).pack(side="left")
        if getattr(item, "progresso", ""):
            tk.Label(
                cabec, text=f"faixa {item.progresso}", bg=PAINEL, fg=AZUL, font=self.fonte_b
            ).pack(side="left", padx=(8, 0))
        if item.forcar != "auto":
            tk.Label(
                cabec, text=f"({item.forcar})", bg=PAINEL, fg=FRACO, font=self.fonte
            ).pack(side="left", padx=(6, 0))

        titulo = item.titulo or item.url
        tk.Label(
            meio, text=titulo[:96], bg=PAINEL, fg=TEXTO, font=self.fonte,
            anchor="w", justify="left",
        ).pack(fill="x")
        if item.detalhe:
            tk.Label(
                meio, text=item.detalhe[:96], bg=PAINEL, fg=FRACO, font=self.mono, anchor="w"
            ).pack(fill="x")

        acoes = tk.Frame(linha, bg=PAINEL)
        acoes.pack(side="right")
        if item.estado == ESPERANDO:
            tk.Button(
                acoes, text="▲", command=lambda i=item.id: self.fila.subir(i),
                bg=PAINEL, fg=FRACO, font=self.mono, relief="flat",
                activebackground=BORDA, cursor="hand2", bd=0, padx=6,
            ).pack(side="left")
        tk.Button(
            acoes, text="✕", command=lambda i=item.id: self.fila.remover(i),
            bg=PAINEL, fg=FRACO, font=self.mono, relief="flat",
            activebackground=VERMELHO, activeforeground="white", cursor="hand2", bd=0, padx=6,
        ).pack(side="left")


def main() -> int:
    raiz = tk.Tk()
    App(raiz)
    raiz.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
