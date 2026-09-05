"""Componentes partilhados pelas páginas."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from . import theme


def aplicar_sombra(alvo: QWidget, desfoque: int = 26, deslocamento: int = 6) -> None:
    """Sombra difusa: separa a superfície do fundo sem a anunciar."""
    sombra = QGraphicsDropShadowEffect(alvo)
    sombra.setBlurRadius(desfoque)
    sombra.setXOffset(0)
    sombra.setYOffset(deslocamento)
    sombra.setColor(QColor(*theme.SOMBRA_COR))
    alvo.setGraphicsEffect(sombra)


class Painel(QFrame):
    """Painel de vidro: material leve, onde o trabalho acontece."""

    def __init__(self, titulo: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("painel")
        aplicar_sombra(self)
        self.corpo = QVBoxLayout(self)
        self.corpo.setContentsMargins(theme.LG, theme.MD + 2, theme.LG, theme.LG)
        self.corpo.setSpacing(theme.SM + 2)
        if titulo:
            etiqueta = QLabel(titulo.upper())
            etiqueta.setObjectName("rotuloSeccao")
            self.corpo.addWidget(etiqueta)


class Conclusao(QFrame):
    """Uma conclusão do diagnóstico: veredicto, medição e recomendação."""

    ROTULOS = {"critico": "FALHA", "alto": "PRIORITÁRIO", "medio": "CAUTELA", "ok": "NOMINAL"}

    def __init__(self, item: dict) -> None:
        super().__init__()
        cor = theme.NIVEL_CORES.get(item.get("nivel", "medio"), theme.CAUTELA)
        # QLabel herda de QFrame: sem o seletor por id, cada rótulo interior
        # apanhava a mesma moldura e a conclusão ficava com caixas repetidas.
        self.setObjectName("conclusao")
        self.setStyleSheet(
            f"QFrame#conclusao {{ background: {theme.ELEVADA};"
            f" border: 1px solid {theme.ARESTA}; border-left: 3px solid {cor};"
            " border-radius: 9px; }"
            " QFrame#conclusao QLabel { border: none; background: transparent; }"
        )
        esquema = QVBoxLayout(self)
        esquema.setContentsMargins(theme.MD + 2, theme.MD - 2, theme.MD + 2, theme.MD - 1)
        esquema.setSpacing(theme.XS)

        cabecalho = QLabel(
            f'<span style="color:{cor};font-family:{theme.FONTE_MONO};font-size:10px;'
            f'font-weight:700;letter-spacing:1px">'
            f'{self.ROTULOS.get(item.get("nivel"), "CAUTELA")}</span>'
            f'&nbsp;&nbsp;<span style="font-weight:600;font-size:13.5px">{item["titulo"]}</span>'
        )
        cabecalho.setWordWrap(True)
        detalhe = QLabel(item["detalhe"])
        detalhe.setWordWrap(True)
        detalhe.setStyleSheet(f"color: {theme.TINTA_SUAVE};")
        acao = QLabel(item["acao"])
        acao.setWordWrap(True)
        acao.setStyleSheet(f"color: {theme.TINTA}; padding-top: {theme.XS}px;")

        esquema.addWidget(cabecalho)
        esquema.addWidget(detalhe)
        esquema.addWidget(acao)


def titulo_pagina(titulo: str, legenda: str) -> QWidget:
    caixa = QWidget()
    caixa.setStyleSheet("background: transparent;")
    esquema = QVBoxLayout(caixa)
    esquema.setContentsMargins(0, 0, 0, 0)
    esquema.setSpacing(3)
    rotulo = QLabel(titulo)
    rotulo.setObjectName("titulo")
    sub = QLabel(legenda)
    sub.setObjectName("legenda")
    sub.setWordWrap(True)
    esquema.addWidget(rotulo)
    esquema.addWidget(sub)
    return caixa


def linha_dados(rotulo: str, valor: str, mono: bool = False) -> QWidget:
    """Linha rótulo/valor. `mono=True` para números e identificadores."""
    caixa = QWidget()
    caixa.setStyleSheet("background: transparent;")
    esquema = QHBoxLayout(caixa)
    esquema.setContentsMargins(0, 2, 0, 2)
    esq = QLabel(rotulo)
    esq.setStyleSheet(f"color: {theme.TINTA_FRACA}; font-size: 12.5px;")
    esq.setMinimumWidth(180)
    esq.setAlignment(Qt.AlignTop | Qt.AlignLeft)
    dir_ = QLabel(str(valor))
    dir_.setWordWrap(True)
    dir_.setTextInteractionFlags(Qt.TextSelectableByMouse)
    dir_.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    if mono:
        dir_.setStyleSheet(f"font-family: {theme.FONTE_MONO}; font-size: 12px;")
    esquema.addWidget(esq)
    esquema.addWidget(dir_, 1)
    return caixa


def separador() -> QFrame:
    linha = QFrame()
    linha.setFrameShape(QFrame.HLine)
    linha.setStyleSheet("background: rgba(255,255,255,0.07); max-height: 1px; border: none;")
    return linha
