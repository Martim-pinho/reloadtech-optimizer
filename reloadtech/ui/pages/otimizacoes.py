"""Página de otimizações e serviços do sistema."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ...core import tweaks
from ...platform_info import IS_WINDOWS, is_admin
from .. import theme
from ..widgets import titulo_pagina
from ..workers import Tarefa


class LinhaOtimizacao(QFrame):
    """Uma otimização: o que faz, o benefício e o botão de aplicar/reverter."""

    executou = Signal(str)

    def __init__(self, tweak: tweaks.Tweak, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.tweak = tweak
        self._tarefa: Tarefa | None = None
        self.setObjectName("painel")

        esquema = QHBoxLayout(self)
        esquema.setContentsMargins(18, 14, 18, 14)
        esquema.setSpacing(14)

        texto = QVBoxLayout()
        texto.setSpacing(3)
        titulo = QLabel(tweak.nome)
        titulo.setStyleSheet("font-weight: 600; font-size: 13.5px; border: none;")
        descricao = QLabel(tweak.descricao)
        descricao.setWordWrap(True)
        descricao.setStyleSheet(f"color: {theme.TINTA_SUAVE}; border: none;")
        beneficio = QLabel(tweak.beneficio)
        beneficio.setWordWrap(True)
        beneficio.setStyleSheet(f"color: {theme.TINTA}; border: none;")
        texto.addWidget(titulo)
        texto.addWidget(descricao)
        texto.addWidget(beneficio)

        marcas = QHBoxLayout()
        marcas.setSpacing(8)
        if tweak.risco != tweaks.BAIXO:
            marcas.addWidget(self._marca("risco médio", theme.CAUTELA))
        if tweak.requires_admin:
            marcas.addWidget(self._marca("administrador", theme.TINTA_SUAVE))
        if tweak.so_servidor:
            marcas.addWidget(self._marca("servidor", theme.LEITURA))
        marcas.addStretch()
        texto.addLayout(marcas)
        esquema.addLayout(texto, 1)

        direita = QVBoxLayout()
        direita.setSpacing(6)
        self.estado = QLabel("")
        self.estado.setAlignment(Qt.AlignRight)
        self.estado.setStyleSheet(f"color: {theme.TINTA_SUAVE}; border: none; font-size: 12px;")
        self.botao = QPushButton("Aplicar")
        self.botao.setMinimumWidth(120)
        self.botao.clicked.connect(self._executar)
        direita.addWidget(self.estado)
        direita.addWidget(self.botao)
        direita.addStretch()
        esquema.addLayout(direita)

        self.atualizar_estado()

    @staticmethod
    def _marca(texto: str, cor: str) -> QLabel:
        etiqueta = QLabel(texto)
        etiqueta.setStyleSheet(
            f"color: {cor}; border: 1px solid {cor}; border-radius: 3px;"
            f"padding: 1px 6px; font-family: {theme.FONTE_MONO};"
            "font-size: 9.5px; font-weight: 600; letter-spacing: .5px;"
        )
        return etiqueta

    def atualizar_estado(self) -> None:
        if self.tweak.tipo == "acao":
            self.estado.setText("ação manual")
            self.botao.setText("Executar")
            self.botao.setObjectName("secundario")
            return
        aplicado = tweaks.state_of(self.tweak)
        if aplicado is True:
            self.estado.setText("✓ aplicada")
            self.estado.setStyleSheet(f"color: {theme.NOMINAL}; border: none; font-size: 12px;")
            self.botao.setText("Reverter")
            self.botao.setObjectName("secundario")
        elif aplicado is False:
            self.estado.setText("por aplicar")
            self.botao.setText("Aplicar")
            self.botao.setObjectName("")
        else:
            self.estado.setText("estado desconhecido")
            self.botao.setText("Aplicar")
        self.botao.style().unpolish(self.botao)
        self.botao.style().polish(self.botao)

    def _executar(self) -> None:
        if self._tarefa and self._tarefa.isRunning():
            return
        aplicado = tweaks.state_of(self.tweak)
        reverter = aplicado is True and self.tweak.tipo != "acao"

        if self.tweak.risco != tweaks.BAIXO and not reverter:
            resposta = QMessageBox.question(
                self, "Confirmar",
                f"{self.tweak.nome}\n\n{self.tweak.descricao}\n\n"
                f"{self.tweak.beneficio}\n\nAplicar agora?",
                QMessageBox.Cancel | QMessageBox.Yes, QMessageBox.Cancel,
            )
            if resposta != QMessageBox.Yes:
                return

        self.botao.setEnabled(False)
        self.botao.setText("A executar…")
        funcao = tweaks.revert if reverter else tweaks.apply
        self._tarefa = Tarefa(funcao, self.tweak, com_progresso=False)
        self._tarefa.terminado.connect(lambda r: self._terminou(r, reverter))
        self._tarefa.falhou.connect(lambda erro: self._terminou((False, erro), reverter))
        self._tarefa.start()

    def _terminou(self, resultado, reverter: bool) -> None:
        ok, mensagem = resultado
        self.botao.setEnabled(True)
        self.atualizar_estado()
        if ok:
            acao = "Revertida" if reverter else "Aplicada"
            self.executou.emit(f"{acao} otimização: {self.tweak.nome}")
        else:
            QMessageBox.critical(self, "Não foi possível concluir",
                                 mensagem or "A operação falhou.")


class PaginaOtimizacoes(QWidget):
    alterou = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(theme.XL, theme.XL, theme.XL, theme.XL)
        raiz.setSpacing(theme.MD)

        raiz.addWidget(titulo_pagina(
            "Otimizações e serviços",
            "Ajustes concretos ao sistema. Cada um diz o que faz e o que ganhas — "
            "os que são interruptores podem ser revertidos aqui mesmo.",
        ))

        if IS_WINDOWS and not is_admin():
            aviso = QLabel(
                "Várias otimizações mexem em serviços do sistema e exigem que abras "
                "a aplicação como administrador."
            )
            aviso.setObjectName("avisoAdmin")
            aviso.setWordWrap(True)
            raiz.addWidget(aviso)

        area = QScrollArea()
        area.setWidgetResizable(True)
        conteudo = QWidget()
        self.esquema = QVBoxLayout(conteudo)
        self.esquema.setContentsMargins(0, 0, 8, 0)
        self.esquema.setSpacing(10)
        area.setWidget(conteudo)
        raiz.addWidget(area, 1)

        disponiveis = tweaks.available_tweaks()
        if not disponiveis:
            vazio = QLabel("Não há otimizações disponíveis para este sistema.")
            vazio.setObjectName("legenda")
            self.esquema.addWidget(vazio)
        for tweak in disponiveis:
            linha = LinhaOtimizacao(tweak)
            linha.executou.connect(self.alterou.emit)
            self.esquema.addWidget(linha)
        self.esquema.addStretch()
