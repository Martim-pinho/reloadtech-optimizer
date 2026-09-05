"""Ícones desenhados a vetor com QPainter.

Sem ficheiros de imagem: os traços são código, ficam nítidos em qualquer
densidade de ecrã e recebem a cor que lhes dermos. Todos partilham a mesma
espessura de traço e a mesma grelha de 24 unidades, para o conjunto se ler
como um só alfabeto.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

GRELHA = 24.0
TRAÇO = 1.7


def _mostrador(caminho: QPainterPath) -> None:
    """Diagnóstico: um mostrador com agulha — o gesto de medir."""
    caminho.arcMoveTo(QRectF(3, 5, 18, 18), 200)
    caminho.arcTo(QRectF(3, 5, 18, 18), 200, -220)
    caminho.moveTo(12, 14)
    caminho.lineTo(16.5, 9.5)


def _pincel(caminho: QPainterPath) -> None:
    """Limpeza: uma escova de bancada."""
    caminho.moveTo(14.5, 3.5)
    caminho.lineTo(9.5, 11.5)
    caminho.moveTo(7, 10)
    caminho.lineTo(14, 14.5)
    caminho.lineTo(11.5, 20.5)
    caminho.lineTo(5.5, 20.5)
    caminho.lineTo(4.5, 14.5)
    caminho.closeSubpath()
    caminho.moveTo(9.2, 16)
    caminho.lineTo(8.4, 20.5)
    caminho.moveTo(16.5, 15.5)
    caminho.lineTo(20, 15.5)
    caminho.moveTo(16, 19)
    caminho.lineTo(19, 20.5)


def _energia(caminho: QPainterPath) -> None:
    """Arranque: o símbolo universal de ligar."""
    caminho.arcMoveTo(QRectF(4, 4, 16, 16), 65)
    caminho.arcTo(QRectF(4, 4, 16, 16), 65, 290)
    caminho.moveTo(12, 3)
    caminho.lineTo(12, 11)


def _cursores(caminho: QPainterPath) -> None:
    """Otimizações: cursores de afinação."""
    for y, x in ((8.0, 15.0), (16.0, 9.0)):
        caminho.moveTo(3.5, y)
        caminho.lineTo(x - 2.6, y)
        caminho.moveTo(x + 2.6, y)
        caminho.lineTo(20.5, y)
        caminho.addEllipse(QPointF(x, y), 2.5, 2.5)


def _documento(caminho: QPainterPath) -> None:
    """Relatório: folha com canto dobrado."""
    caminho.moveTo(14, 3.5)
    caminho.lineTo(6.5, 3.5)
    caminho.lineTo(6.5, 20.5)
    caminho.lineTo(17.5, 20.5)
    caminho.lineTo(17.5, 7)
    caminho.closeSubpath()
    caminho.moveTo(14, 3.5)
    caminho.lineTo(17.5, 7)
    caminho.moveTo(9.5, 12)
    caminho.lineTo(14.5, 12)
    caminho.moveTo(9.5, 16)
    caminho.lineTo(14.5, 16)


DESENHOS = {
    "diagnostico": _mostrador,
    "limpeza": _pincel,
    "arranque": _energia,
    "otimizacoes": _cursores,
    "relatorio": _documento,
}


def pixmap(nome: str, cor: str, tamanho: int = 18, dpr: float = 2.0) -> QPixmap:
    lado = int(tamanho * dpr)
    imagem = QPixmap(lado, lado)
    imagem.fill(Qt.transparent)

    pintor = QPainter(imagem)
    pintor.setRenderHint(QPainter.Antialiasing)
    pintor.scale(lado / GRELHA, lado / GRELHA)

    caneta = QPen(QColor(cor))
    caneta.setWidthF(TRAÇO)
    caneta.setCapStyle(Qt.RoundCap)
    caneta.setJoinStyle(Qt.RoundJoin)
    pintor.setPen(caneta)
    pintor.setBrush(Qt.NoBrush)

    caminho = QPainterPath()
    DESENHOS[nome](caminho)
    pintor.drawPath(caminho)
    pintor.end()

    imagem.setDevicePixelRatio(dpr)
    return imagem


def icone(nome: str, cor_normal: str, cor_ativa: str, tamanho: int = 18) -> QIcon:
    """Ícone com dois estados: apagado na barra, aceso quando selecionado."""
    resultado = QIcon()
    resultado.addPixmap(pixmap(nome, cor_normal, tamanho), QIcon.Normal, QIcon.Off)
    resultado.addPixmap(pixmap(nome, cor_ativa, tamanho), QIcon.Normal, QIcon.On)
    resultado.addPixmap(pixmap(nome, cor_ativa, tamanho), QIcon.Active, QIcon.Off)
    return resultado
