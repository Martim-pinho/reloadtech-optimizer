"""Escalas calibradas desenhadas à mão.

O elemento que distingue esta ferramenta: em vez de mostrar «81%» numa caixa,
mostra onde 81% cai numa régua graduada, com o limiar de atenção marcado. O
técnico vê a medida e o critério ao mesmo tempo — e o cliente percebe que o
número não foi inventado.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from . import theme

MONO = ["JetBrains Mono", "SF Mono", "Menlo", "Cascadia Mono", "Consolas",
        "DejaVu Sans Mono", "Courier New"]
UI = ["Inter", "SF Pro Text", "Segoe UI Variable Text", "Segoe UI", "Helvetica Neue",
      "DejaVu Sans"]


def fonte(familias: list[str], tamanho: float, peso: QFont.Weight = QFont.Normal,
          espacamento: float = 0.0) -> QFont:
    letra = QFont()
    letra.setFamilies(familias)
    letra.setPointSizeF(tamanho)
    letra.setWeight(peso)
    if espacamento:
        letra.setLetterSpacing(QFont.AbsoluteSpacing, espacamento)
    return letra


class Medidor(QWidget):
    """Leitura compacta: rótulo, valor monoespaçado e régua graduada."""

    def __init__(self, rotulo: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rotulo = rotulo
        self._valor = 0.0
        self._texto = "—"
        self._detalhe = ""
        self._invertido = False
        self._limiar: float | None = theme.LIMIAR_ATENCAO
        self.setMinimumHeight(64)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def definir(self, valor: float, texto: str, detalhe: str = "",
                invertido: bool = False, limiar: float | None = theme.LIMIAR_ATENCAO) -> None:
        self._valor = max(0.0, min(100.0, float(valor)))
        self._texto = texto
        self._detalhe = detalhe
        self._invertido = invertido
        self._limiar = limiar
        self.update()

    def paintEvent(self, _evento) -> None:  # noqa: N802 - assinatura do Qt
        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.Antialiasing)
        largura = self.width()
        cor = QColor(theme.cor_medicao(self._valor, self._invertido))

        # Linha superior: rótulo à esquerda, leitura à direita
        pintor.setFont(fonte(MONO, 7.5, QFont.DemiBold, 1.1))
        pintor.setPen(QColor(theme.TINTA_SUAVE))
        pintor.drawText(QRectF(0, 0, largura, 14), Qt.AlignLeft | Qt.AlignVCenter,
                        self._rotulo.upper())

        pintor.setFont(fonte(MONO, 12.5, QFont.DemiBold))
        pintor.setPen(cor)
        pintor.drawText(QRectF(0, -1, largura, 18), Qt.AlignRight | Qt.AlignVCenter, self._texto)

        # Régua
        topo = 26.0
        altura = 6.0
        pintor.setPen(Qt.NoPen)
        pintor.setBrush(QColor(theme.TRILHO))
        pintor.drawRoundedRect(QRectF(0, topo, largura, altura), 3, 3)

        preenchido = largura * self._valor / 100.0
        if preenchido > 0:
            pintor.setBrush(cor)
            pintor.drawRoundedRect(QRectF(0, topo, max(preenchido, 3.0), altura), 3, 3)

        # Graduação de 10 em 10, mais alta nos quartos
        caneta = QPen(QColor("#c9cec6"))
        caneta.setWidthF(1.0)
        pintor.setPen(caneta)
        for passo in range(0, 11):
            x = largura * passo / 10.0
            x = min(max(x, 0.5), largura - 0.5)
            comprimento = 5.0 if passo % 5 == 0 else 3.0
            pintor.drawLine(QPointF(x, topo + altura + 2), QPointF(x, topo + altura + 2 + comprimento))

        # Limiar: o critério fica à vista, não escondido no código
        if self._limiar is not None:
            x = largura * self._limiar / 100.0
            caneta = QPen(QColor(theme.TINTA_SUAVE))
            caneta.setWidthF(1.0)
            caneta.setStyle(Qt.DotLine)
            pintor.setPen(caneta)
            pintor.drawLine(QPointF(x, topo - 4), QPointF(x, topo + altura + 4))

        if self._detalhe:
            pintor.setFont(fonte(UI, 8.5))
            pintor.setPen(QColor(theme.TINTA_SUAVE))
            pintor.drawText(QRectF(0, topo + altura + 8, largura, 16),
                            Qt.AlignLeft | Qt.AlignVCenter, self._detalhe)
        pintor.end()


class EscalaSaude(QWidget):
    """Escala 0–100 do índice de saúde, com as três zonas de avaliação à vista."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._valor: int | None = None
        self.setMinimumHeight(112)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def definir(self, valor: int | None) -> None:
        self._valor = valor
        self.update()

    def paintEvent(self, _evento) -> None:  # noqa: N802 - assinatura do Qt
        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.Antialiasing)
        largura = self.width()
        valor = self._valor
        cor = QColor(theme.cor_medicao(valor if valor is not None else 0, invertido=True)) \
            if valor is not None else QColor(theme.TINTA_SUAVE)

        pintor.setFont(fonte(MONO, 7.5, QFont.DemiBold, 1.1))
        pintor.setPen(QColor(theme.TINTA_SUAVE))
        pintor.drawText(QRectF(0, 0, largura, 14), Qt.AlignLeft | Qt.AlignVCenter,
                        "ÍNDICE DE SAÚDE DO SISTEMA")

        # Leitura principal
        pintor.setFont(fonte(MONO, 30, QFont.Bold))
        pintor.setPen(cor)
        texto = str(valor) if valor is not None else "––"
        pintor.drawText(QRectF(0, 16, largura, 42), Qt.AlignLeft | Qt.AlignVCenter, texto)
        largura_valor = pintor.fontMetrics().horizontalAdvance(texto)

        pintor.setFont(fonte(MONO, 10))
        pintor.setPen(QColor(theme.TINTA_SUAVE))
        pintor.drawText(QRectF(largura_valor + 7, 16, 120, 42), Qt.AlignLeft | Qt.AlignVCenter, "/100")

        if valor is not None:
            pintor.setFont(fonte(UI, 9.5))
            pintor.setPen(QColor(theme.TINTA_SUAVE))
            legenda = ("dentro dos valores normais" if valor >= theme.LIMIAR_ATENCAO
                       else "requer atenção" if valor >= 50 else "intervenção necessária")
            pintor.drawText(QRectF(largura_valor + 52, 16, largura, 42),
                            Qt.AlignLeft | Qt.AlignVCenter, legenda)

        # Régua com as três zonas de avaliação.
        # Não se preenche até ao valor: isto é uma escala, não uma barra de
        # progresso. Preencher taparia as zonas, que são o que dá sentido ao
        # número — o valor entra pelo marcador.
        topo = 68.0
        altura = 8.0
        zonas = [(0, 50, theme.FALHA), (50, theme.LIMIAR_ATENCAO, theme.CAUTELA),
                 (theme.LIMIAR_ATENCAO, 100, theme.NOMINAL)]
        pintor.setPen(Qt.NoPen)
        for inicio, fim, cor_zona in zonas:
            tinta = QColor(cor_zona)
            tinta.setAlpha(92)
            pintor.setBrush(tinta)
            x0 = largura * inicio / 100.0
            pintor.drawRect(QRectF(x0, topo, largura * (fim - inicio) / 100.0, altura))

        caneta = QPen(QColor("#c9cec6"))
        caneta.setWidthF(1.0)
        pintor.setPen(caneta)
        for passo in range(0, 21):
            x = min(max(largura * passo / 20.0, 0.5), largura - 0.5)
            comprimento = 5.0 if passo % 5 == 0 else 2.5
            pintor.drawLine(QPointF(x, topo + altura + 2), QPointF(x, topo + altura + 2 + comprimento))

        # Marcador: agulha do instrumento sobre a zona onde o valor caiu
        if valor is not None:
            x = min(max(largura * valor / 100.0, 1.0), largura - 1.0)
            pintor.setPen(Qt.NoPen)
            pintor.setBrush(QColor(255, 255, 255, 235))
            pintor.drawRect(QRectF(x - 1.5, topo, 3.0, altura))
            pintor.setBrush(cor)
            pintor.drawRect(QRectF(x - 0.75, topo, 1.5, altura))
            seta = QPainterPath()
            seta.moveTo(x, topo - 1.5)
            seta.lineTo(x - 5.0, topo - 9)
            seta.lineTo(x + 5.0, topo - 9)
            seta.closeSubpath()
            pintor.setBrush(cor)
            pintor.drawPath(seta)

        # Fronteiras das zonas, rotuladas
        pintor.setFont(fonte(MONO, 7.5))
        pintor.setPen(QColor(theme.TINTA_SUAVE))
        for marca in (0, 50, theme.LIMIAR_ATENCAO, 100):
            x = largura * marca / 100.0
            caixa = QRectF(x - 20, topo + altura + 9, 40, 12)
            alinhamento = Qt.AlignCenter
            if marca == 0:
                caixa = QRectF(0, topo + altura + 9, 40, 12)
                alinhamento = Qt.AlignLeft | Qt.AlignVCenter
            elif marca == 100:
                caixa = QRectF(largura - 40, topo + altura + 9, 40, 12)
                alinhamento = Qt.AlignRight | Qt.AlignVCenter
            pintor.drawText(caixa, alinhamento, str(marca))
        pintor.end()
