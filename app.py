#!/usr/bin/env python3
"""Interface grafica moderna e responsiva em PySide6 para o Baixador YouTube / YT Music.

Recursos:
- Layout fluido e 100% responsivo
- Tema escuro moderno (Palette Indigo & Slate)
- Seletor alternavel MP3 (Audio) / MP4 (Video)
- Suporte a links individuais, playlists e links do YT Music
- Fila sequencial em segundo plano com controle de pausa/retomada
- Integracao total com banco SQLite (historico.db) para zero duplicatas
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QThread, QTimer, QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices, QFont, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

from ytdl.comum import carregar_config, preparar_console
from ytdl.fila import (
    BAIXANDO,
    CANCELADO,
    CONCLUIDO,
    ESPERANDO,
    FALHOU,
    Fila,
    Item,
)

CORES = {
    ESPERANDO: "#64748b",
    BAIXANDO: "#f59e0b",
    CONCLUIDO: "#10b981",
    FALHOU: "#ef4444",
    CANCELADO: "#475569",
}

ROTULOS = {
    ESPERANDO: "Na fila",
    BAIXANDO: "Baixando",
    CONCLUIDO: "Concluído",
    FALHOU: "Falhou",
    CANCELADO: "Cancelado",
}

QSS = """
QMainWindow, QWidget#root {
    background-color: #0f172a;
    color: #f8fafc;
    font-family: "Segoe UI", -apple-system, sans-serif;
}

QFrame#card {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 10px;
}

QLineEdit#urlInput {
    background-color: #0f172a;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 10px 14px;
    color: #f8fafc;
    font-size: 13px;
}
QLineEdit#urlInput:focus {
    border: 1px solid #6366f1;
}

QFrame#switchFrame {
    background-color: #0f172a;
    border: 1px solid #334155;
    border-radius: 8px;
}

QRadioButton#modeRadio {
    color: #94a3b8;
    font-weight: bold;
    font-size: 12px;
    padding: 6px 14px;
    border-radius: 6px;
}
QRadioButton#modeRadio::indicator {
    width: 0px;
    height: 0px;
}
QRadioButton#modeRadio:checked {
    background-color: #6366f1;
    color: #ffffff;
}

QComboBox#customCombo {
    background-color: #0f172a;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 6px 12px;
    color: #cbd5e1;
    font-size: 12px;
}
QComboBox#customCombo::drop-down {
    border: none;
}

QPushButton#addBtn {
    background-color: #6366f1;
    color: #ffffff;
    border: none;
    border-radius: 8px;
    padding: 10px 20px;
    font-weight: bold;
    font-size: 13px;
}
QPushButton#addBtn:hover {
    background-color: #4f46e5;
}
QPushButton#addBtn:pressed {
    background-color: #4338ca;
}

QPushButton#actionBtn {
    background-color: #334155;
    color: #f1f5f9;
    border: none;
    border-radius: 6px;
    padding: 6px 12px;
    font-weight: 600;
    font-size: 12px;
}
QPushButton#actionBtn:hover {
    background-color: #475569;
}

QPushButton#iconBtn {
    background-color: transparent;
    color: #94a3b8;
    border: none;
    border-radius: 4px;
    font-size: 13px;
    padding: 4px 8px;
}
QPushButton#iconBtn:hover {
    background-color: #334155;
    color: #ffffff;
}

QScrollArea {
    border: none;
    background-color: transparent;
}

QScrollBar:vertical {
    border: none;
    background: #0f172a;
    width: 8px;
    margin: 0px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #334155;
    min-height: 20px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: #475569;
}

QTextEdit#logBox {
    background-color: #0f172a;
    border: 1px solid #334155;
    border-radius: 8px;
    color: #94a3b8;
    font-family: "Consolas", monospace;
    font-size: 11px;
}
"""


class SignalBridge(QObject):
    queue_updated = Signal()
    log_added = Signal(str)


class ItemWidget(QFrame):
    def __init__(self, item: Item, parent_app: AppMainWindow):
        super().__init__()
        self.item = item
        self.parent_app = parent_app
        self.setObjectName("card")
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)

        # Barra lateral de status
        self.accent = QFrame()
        self.accent.setFixedWidth(4)
        self.accent.setStyleSheet(
            f"background-color: {CORES.get(self.item.estado, '#64748b')}; border-radius: 2px;"
        )
        layout.addWidget(self.accent)

        # Informacoes centrais
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        # Badge do modo (MP3/MP4)
        mode_badge = QLabel(self.item.modo.upper())
        mode_badge.setStyleSheet(
            "background-color: #334155; color: #f8fafc; font-weight: bold; "
            "font-size: 10px; padding: 2px 6px; border-radius: 4px;"
        )
        top_row.addWidget(mode_badge)

        # Status
        status_lbl = QLabel(ROTULOS.get(self.item.estado, self.item.estado))
        status_lbl.setStyleSheet(
            f"color: {CORES.get(self.item.estado, '#94a3b8')}; font-weight: bold; font-size: 12px;"
        )
        top_row.addWidget(status_lbl)

        # Progresso da playlist (ex: 2/15)
        if getattr(self.item, "progresso", ""):
            prog_lbl = QLabel(f"Faixa {self.item.progresso}")
            prog_lbl.setStyleSheet(
                "color: #818cf8; font-weight: bold; font-size: 11px;"
            )
            top_row.addWidget(prog_lbl)

        if self.item.forcar != "auto":
            opt_lbl = QLabel(f"({self.item.forcar})")
            opt_lbl.setStyleSheet("color: #64748b; font-size: 11px;")
            top_row.addWidget(opt_lbl)

        top_row.addStretch()
        info_layout.addLayout(top_row)

        # Titulo do video/musica
        titulo_texto = self.item.titulo or self.item.url
        title_lbl = QLabel(titulo_texto)
        title_lbl.setStyleSheet(
            "color: #f8fafc; font-size: 13px; font-weight: 500;"
        )
        title_lbl.setWordWrap(True)
        info_layout.addWidget(title_lbl)

        # Detalhe do status
        if self.item.detalhe:
            det_lbl = QLabel(self.item.detalhe)
            det_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")
            info_layout.addWidget(det_lbl)

        layout.addLayout(info_layout, stretch=1)

        # Botoes de acao
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(4)

        if self.item.estado == ESPERANDO:
            up_btn = QPushButton("▲")
            up_btn.setObjectName("iconBtn")
            up_btn.setToolTip("Subir na fila")
            up_btn.clicked.connect(lambda: self.parent_app.subir_item(self.item.id))
            btn_layout.addWidget(up_btn)

        del_btn = QPushButton("✕")
        del_btn.setObjectName("iconBtn")
        del_btn.setStyleSheet("QPushButton#iconBtn:hover { color: #ef4444; }")
        del_btn.setToolTip("Remover da fila")
        del_btn.clicked.connect(lambda: self.parent_app.remover_item(self.item.id))
        btn_layout.addWidget(del_btn)

        layout.addLayout(btn_layout)


class AppMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        preparar_console()
        self.setWindowTitle("Baixador de Músicas e Vídeos")
        self.resize(900, 680)
        self.setMinimumSize(740, 520)

        self.bridge = SignalBridge()
        self.bridge.queue_updated.connect(self._on_queue_updated)
        self.bridge.log_added.connect(self._on_log_added)

        self.fila = Fila(
            ao_mudar=self.bridge.queue_updated.emit,
            ao_log=self.bridge.log_added.emit,
        )

        self._build_ui()
        self._refresh_queue_ui()
        self.fila.iniciar()

    def _build_ui(self):
        central = QWidget()
        central.setObjectName("root")
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        # --- HEADER ---
        header = QHBoxLayout()
        header_info = QVBoxLayout()
        header_info.setSpacing(2)

        title = QLabel("Baixador de Músicas e Vídeos")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #f8fafc;")
        subtitle = QLabel("YouTube, YouTube Music, TikTok, Instagram e outros")
        subtitle.setStyleSheet("font-size: 12px; color: #64748b;")

        header_info.addWidget(title)
        header_info.addWidget(subtitle)
        header.addLayout(header_info)
        header.addStretch()

        # Botoes de pastas
        cfg = carregar_config()
        btn_music = QPushButton("📁 Músicas")
        btn_music.setObjectName("actionBtn")
        btn_music.clicked.connect(lambda: self._open_folder(cfg["pasta_mp3"]))
        header.addWidget(btn_music)

        btn_video = QPushButton("📁 Vídeos")
        btn_video.setObjectName("actionBtn")
        btn_video.clicked.connect(lambda: self._open_folder(cfg["pasta_mp4"]))
        header.addWidget(btn_video)

        main_layout.addLayout(header)

        # --- INPUT CARD ---
        input_card = QFrame()
        input_card.setObjectName("card")
        input_layout = QVBoxLayout(input_card)
        input_layout.setContentsMargins(16, 16, 16, 16)
        input_layout.setSpacing(12)

        row1 = QHBoxLayout()
        row1.setSpacing(10)

        self.url_input = QLineEdit()
        self.url_input.setObjectName("urlInput")
        self.url_input.setPlaceholderText(
            "Cole aqui a URL (ex: https://music.youtube.com/watch?v=... ou playlist)"
        )
        self.url_input.returnPressed.connect(self._add_url)
        row1.addWidget(self.url_input, stretch=1)

        # Seletor de Modo Switch (MP3 / MP4)
        switch_frame = QFrame()
        switch_frame.setObjectName("switchFrame")
        switch_layout = QHBoxLayout(switch_frame)
        switch_layout.setContentsMargins(4, 4, 4, 4)
        switch_layout.setSpacing(2)

        self.mode_group = QButtonGroup(self)
        self.rb_mp3 = QRadioButton("🎵 MP3")
        self.rb_mp3.setObjectName("modeRadio")
        self.rb_mp3.setChecked(True)
        self.rb_mp4 = QRadioButton("🎬 MP4")
        self.rb_mp4.setObjectName("modeRadio")

        self.mode_group.addButton(self.rb_mp3)
        self.mode_group.addButton(self.rb_mp4)

        switch_layout.addWidget(self.rb_mp3)
        switch_layout.addWidget(self.rb_mp4)
        row1.addWidget(switch_frame)

        # Botao Adicionar
        self.add_btn = QPushButton("+ Adicionar à Fila")
        self.add_btn.setObjectName("addBtn")
        self.add_btn.setCursor(Qt.PointingHandCursor)
        self.add_btn.clicked.connect(self._add_url)
        row1.addWidget(self.add_btn)

        input_layout.addLayout(row1)
        main_layout.addWidget(input_card)

        # --- CONTROLES DA FILA ---
        queue_header = QHBoxLayout()
        self.queue_label = QLabel("FILA DE DOWNLOADS")
        self.queue_label.setStyleSheet(
            "font-size: 13px; font-weight: bold; color: #94a3b8; letter-spacing: 0.5px;"
        )
        queue_header.addWidget(self.queue_label)
        queue_header.addStretch()

        self.btn_pause = QPushButton("Pausar Fila")
        self.btn_pause.setObjectName("actionBtn")
        self.btn_pause.clicked.connect(self._toggle_pause)
        queue_header.addWidget(self.btn_pause)

        btn_retry = QPushButton("🔄 Re-tentar Falhas")
        btn_retry.setObjectName("actionBtn")
        btn_retry.clicked.connect(self._retry_failed)
        queue_header.addWidget(btn_retry)

        btn_clear = QPushButton("Limpar Concluídos")
        btn_clear.setObjectName("actionBtn")
        btn_clear.clicked.connect(self._clear_finished)
        queue_header.addWidget(btn_clear)

        main_layout.addLayout(queue_header)

        # --- SCROLL AREA DA FILA ---
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)

        self.queue_container = QWidget()
        self.queue_container.setStyleSheet("background-color: transparent;")
        self.queue_layout = QVBoxLayout(self.queue_container)
        self.queue_layout.setContentsMargins(0, 0, 0, 0)
        self.queue_layout.setSpacing(8)
        self.queue_layout.addStretch()

        self.scroll_area.setWidget(self.queue_container)
        main_layout.addWidget(self.scroll_area, stretch=1)

        # --- LOG CONSOLE ---
        log_header = QHBoxLayout()
        log_label = QLabel("LOGS DO SISTEMA")
        log_label.setStyleSheet(
            "font-size: 12px; font-weight: bold; color: #64748b;"
        )
        log_header.addWidget(log_label)
        log_header.addStretch()

        self.btn_toggle_log = QPushButton("Ocultar Logs")
        self.btn_toggle_log.setObjectName("actionBtn")
        self.btn_toggle_log.clicked.connect(self._toggle_log_box)
        log_header.addWidget(self.btn_toggle_log)
        main_layout.addLayout(log_header)

        self.log_box = QTextEdit()
        self.log_box.setObjectName("logBox")
        self.log_box.setReadOnly(True)
        self.log_box.setMaximumHeight(140)
        main_layout.addWidget(self.log_box)

    # --- ACTIONS ---
    def _add_url(self):
        text = self.url_input.text().strip()
        if not text:
            return

        modo = "mp3" if self.rb_mp3.isChecked() else "mp4"
        forcar = "auto"

        added = 0
        for url in text.replace("\n", " ").split():
            if self.fila.adicionar(url, modo, forcar):
                added += 1

        if added > 0:
            self.url_input.clear()
            self._on_log_added(f"+ {added} link(s) adicionados à fila em modo {modo.upper()}")
        else:
            self._on_log_added("! Link inválido ou já existente na fila")

    def _toggle_pause(self):
        if self.fila.pausado:
            self.fila.iniciar()
        else:
            self.fila.pausar()
        self._refresh_queue_ui()

    def _retry_failed(self):
        count = self.fila.retentar_falhas()
        if count > 0:
            self._on_log_added(f"+ {count} item(ns) recolocados na fila para nova tentativa")
        else:
            self._on_log_added("! Nenhum item com falha para re-tentar")

    def _clear_finished(self):
        self.fila.limpar_terminados()
        self._refresh_queue_ui()

    def _open_folder(self, path_str: str):
        path = Path(path_str).expanduser()
        path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def subir_item(self, item_id: int):
        self.fila.subir(item_id)

    def remover_item(self, item_id: int):
        self.fila.remover(item_id)

    def _toggle_log_box(self):
        visible = self.log_box.isVisible()
        self.log_box.setVisible(not visible)
        self.btn_toggle_log.setText("Mostrar Logs" if visible else "Ocultar Logs")

    # --- SLOTS DE ATUALIZACAO ---
    def _on_queue_updated(self):
        self._refresh_queue_ui()

    def _on_log_added(self, msg: str):
        if msg.strip():
            self.log_box.append(msg)

    def _refresh_queue_ui(self):
        # Limpa widgets anteriores
        while self.queue_layout.count() > 1:
            child = self.queue_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        itens = list(self.fila.itens)
        esperando = sum(1 for i in itens if i.estado == ESPERANDO)
        concluidos = sum(1 for i in itens if i.estado == CONCLUIDO)

        self.queue_label.setText(
            f"FILA DE DOWNLOADS — {esperando} aguardando, {concluidos} concluídos ({len(itens)} total)"
        )
        self.btn_pause.setText("Retomar Fila" if self.fila.pausado else "Pausar Fila")

        if not itens:
            empty_lbl = QLabel(
                "\nNenhum download na fila.\nCole um link acima e clique em 'Adicionar à Fila'.\n"
            )
            empty_lbl.setAlignment(Qt.AlignCenter)
            empty_lbl.setStyleSheet("color: #64748b; font-size: 13px;")
            self.queue_layout.insertWidget(0, empty_lbl)
            return

        for idx, item in enumerate(itens):
            w = ItemWidget(item, self)
            self.queue_layout.insertWidget(idx, w)

    def closeEvent(self, event):
        self.fila.parar_agora()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(QSS)
    win = AppMainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
