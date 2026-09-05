"""Página de limpeza: analisa, mostra o que vai ser apagado e só depois limpa."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...core import cleaner
from ...platform_info import human_bytes
from .. import theme
from ..widgets import titulo_pagina
from ..workers import Tarefa


class PaginaLimpeza(QWidget):
    limpou = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._resultados: list[cleaner.ScanResult] = []
        self._tarefa: Tarefa | None = None

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(theme.XL, theme.XL, theme.XL, theme.XL)
        raiz.setSpacing(theme.MD)

        topo = QHBoxLayout()
        topo.addWidget(titulo_pagina(
            "Limpeza de ficheiros",
            "Só são removidos ficheiros temporários e caches. "
            "Documentos, transferências e definições nunca são tocados.",
        ), 1)
        self.botao_analisar = QPushButton("Analisar")
        self.botao_analisar.setObjectName("primario")
        self.botao_analisar.clicked.connect(self.analisar)
        topo.addWidget(self.botao_analisar, 0, Qt.AlignTop)
        raiz.addLayout(topo)

        self.barra = QProgressBar()
        self.barra.setTextVisible(False)
        self.barra.hide()
        raiz.addWidget(self.barra)

        self.arvore = QTreeWidget()
        self.arvore.setHeaderLabels(["Alvo", "Espaço", "Ficheiros", "Risco"])
        self.arvore.setRootIsDecorated(False)
        self.arvore.setAlternatingRowColors(True)
        self.arvore.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.arvore.itemChanged.connect(self._atualizar_total)
        raiz.addWidget(self.arvore, 1)

        self.descricao = QLabel("Seleciona uma linha para ver o que inclui.")
        self.descricao.setObjectName("legenda")
        self.descricao.setWordWrap(True)
        self.arvore.currentItemChanged.connect(self._mostrar_descricao)
        raiz.addWidget(self.descricao)

        rodape = QHBoxLayout()
        self.total = QLabel("Nada analisado ainda.")
        self.total.setStyleSheet("font-size: 15px; font-weight: 600;")
        rodape.addWidget(self.total, 1)
        self.botao_selecionar = QPushButton("Selecionar apenas os seguros")
        self.botao_selecionar.setObjectName("secundario")
        self.botao_selecionar.clicked.connect(self._selecionar_seguros)
        self.botao_selecionar.setEnabled(False)
        self.botao_limpar = QPushButton("Limpar selecionados")
        self.botao_limpar.setObjectName("perigo")
        self.botao_limpar.clicked.connect(self.limpar)
        self.botao_limpar.setEnabled(False)
        rodape.addWidget(self.botao_selecionar)
        rodape.addWidget(self.botao_limpar)
        raiz.addLayout(rodape)

    # --- Análise -------------------------------------------------------------

    def analisar(self) -> None:
        if self._tarefa and self._tarefa.isRunning():
            return
        self.botao_analisar.setEnabled(False)
        self.botao_analisar.setText("A analisar…")
        self.barra.setValue(0)
        self.barra.show()
        self.arvore.clear()

        self._tarefa = Tarefa(cleaner.scan)
        self._tarefa.progresso.connect(lambda pct, _t: self.barra.setValue(pct))
        self._tarefa.terminado.connect(self._mostrar)
        self._tarefa.falhou.connect(self._erro)
        self._tarefa.start()

    def _erro(self, mensagem: str) -> None:
        self.botao_analisar.setEnabled(True)
        self.botao_analisar.setText("Analisar")
        self.barra.hide()
        self.total.setText(f"Falhou: {mensagem}")

    def _mostrar(self, resultados: list[cleaner.ScanResult]) -> None:
        self._resultados = sorted(resultados, key=lambda r: r.bytes, reverse=True)
        self.botao_analisar.setEnabled(True)
        self.botao_analisar.setText("Analisar de novo")
        self.barra.hide()
        self.arvore.clear()

        for resultado in self._resultados:
            item = QTreeWidgetItem([
                resultado.target.nome,
                resultado.readable,
                str(resultado.files) if resultado.files else "—",
                "Seguro" if resultado.target.risco == cleaner.SAFE else "Rever antes",
            ])
            item.setData(0, Qt.UserRole, resultado)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            pode = resultado.bytes > 0 and not resultado.error
            item.setCheckState(0, Qt.Checked if pode and resultado.target.risco == cleaner.SAFE else Qt.Unchecked)
            if resultado.target.risco != cleaner.SAFE:
                item.setForeground(3, Qt.GlobalColor.darkYellow)
            if resultado.error:
                item.setText(1, resultado.error)
                item.setDisabled(True)
            self.arvore.addTopLevelItem(item)

        self.botao_limpar.setEnabled(True)
        self.botao_selecionar.setEnabled(True)
        self._atualizar_total()

    def _mostrar_descricao(self, atual: QTreeWidgetItem | None) -> None:
        if atual is None:
            return
        resultado = atual.data(0, Qt.UserRole)
        if resultado:
            self.descricao.setText(resultado.target.descricao)

    def _selecionar_seguros(self) -> None:
        for indice in range(self.arvore.topLevelItemCount()):
            item = self.arvore.topLevelItem(indice)
            resultado = item.data(0, Qt.UserRole)
            seguro = resultado and resultado.target.risco == cleaner.SAFE and resultado.bytes > 0
            item.setCheckState(0, Qt.Checked if seguro else Qt.Unchecked)

    def _selecionados(self) -> list[cleaner.CleanTarget]:
        alvos = []
        for indice in range(self.arvore.topLevelItemCount()):
            item = self.arvore.topLevelItem(indice)
            if item.checkState(0) == Qt.Checked:
                resultado = item.data(0, Qt.UserRole)
                if resultado:
                    alvos.append(resultado.target)
        return alvos

    def _atualizar_total(self) -> None:
        total = 0
        for indice in range(self.arvore.topLevelItemCount()):
            item = self.arvore.topLevelItem(indice)
            if item.checkState(0) == Qt.Checked:
                resultado = item.data(0, Qt.UserRole)
                if resultado:
                    total += resultado.bytes
        encontrado = sum(r.bytes for r in self._resultados)
        self.total.setText(
            f"Selecionado: {human_bytes(total)}   "
            f"<span style='color:{theme.TINTA_SUAVE};font-weight:400'>"
            f"(encontrado no total: {human_bytes(encontrado)})</span>"
        )
        self.total.setTextFormat(Qt.RichText)
        self.botao_limpar.setEnabled(total > 0)

    # --- Limpeza -------------------------------------------------------------

    def limpar(self) -> None:
        alvos = self._selecionados()
        if not alvos:
            return
        total = sum(r.bytes for r in self._resultados if r.target in alvos)
        arriscados = [a.nome for a in alvos if a.risco != cleaner.SAFE]

        texto = f"Vão ser apagados {human_bytes(total)} em {len(alvos)} categorias."
        if arriscados:
            texto += "\n\nInclui alvos que convém rever:\n• " + "\n• ".join(arriscados)
        texto += "\n\nEsta operação não pode ser anulada. Continuar?"

        confirmacao = QMessageBox(self)
        confirmacao.setWindowTitle("Confirmar limpeza")
        confirmacao.setText(texto)
        confirmacao.setIcon(QMessageBox.Warning)
        confirmacao.setStandardButtons(QMessageBox.Cancel | QMessageBox.Yes)
        confirmacao.setDefaultButton(QMessageBox.Cancel)
        confirmacao.button(QMessageBox.Yes).setText("Limpar")
        confirmacao.button(QMessageBox.Cancel).setText("Cancelar")
        if confirmacao.exec() != QMessageBox.Yes:
            return

        self.botao_limpar.setEnabled(False)
        self.botao_analisar.setEnabled(False)
        self.barra.setValue(0)
        self.barra.show()

        self._tarefa = Tarefa(cleaner.clean, alvos)
        self._tarefa.progresso.connect(lambda pct, _t: self.barra.setValue(pct))
        self._tarefa.terminado.connect(self._limpeza_terminada)
        self._tarefa.falhou.connect(self._erro)
        self._tarefa.start()

    def _limpeza_terminada(self, resultados: list[cleaner.ScanResult]) -> None:
        libertado = sum(r.bytes for r in resultados)
        self.barra.hide()
        self.botao_analisar.setEnabled(True)
        self.total.setText(f"Libertado: {human_bytes(libertado)}")
        self.limpou.emit(f"Limpeza de ficheiros temporários: {human_bytes(libertado)} libertados")
        QMessageBox.information(
            self, "Limpeza concluída",
            f"Foram libertados {human_bytes(libertado)}.\n\n"
            "Ficheiros em uso por programas abertos são ignorados — é normal e não é erro.",
        )
        self.analisar()
