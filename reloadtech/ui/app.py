"""Janela principal e arranque da interface gráfica."""
from __future__ import annotations

import platform
import socket
import sys

from PySide6.QtCore import QEasingCurve, QPointF, QPropertyAnimation, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QRadialGradient
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..platform_info import (
    APP_NAME,
    APP_VERSION,
    BRAND,
    IS_WINDOWS,
    is_admin,
    os_label,
    reduced_motion,
)
from . import theme
from .pages.arranque import PaginaArranque
from .pages.diagnostico import PaginaDiagnostico
from .pages.limpeza import PaginaLimpeza
from .pages.otimizacoes import PaginaOtimizacoes
from .pages.relatorio import PaginaRelatorio


class Fundo(QWidget):
    """Fundo da janela: gradiente de baixa frequência com um foco de luz.

    É o que dá aos painéis translúcidos algo por onde deixar passar. Um
    cinzento chapado não daria nada — o vidro só se lê contra variação.
    """

    def paintEvent(self, _evento) -> None:  # noqa: N802 - assinatura do Qt
        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.Antialiasing)
        area = self.rect()

        vertical = QLinearGradient(QPointF(area.topLeft()), QPointF(area.bottomLeft()))
        vertical.setColorAt(0.0, QColor(theme.FUNDO_TOPO))
        vertical.setColorAt(1.0, QColor(theme.FUNDO_BASE))
        pintor.fillRect(area, vertical)

        luz = QRadialGradient(QPointF(area.width() * 0.24, area.height() * -0.12),
                              area.width() * 0.95)
        luz.setColorAt(0.0, QColor(255, 255, 255, 150))
        luz.setColorAt(1.0, QColor(255, 255, 255, 0))
        pintor.fillRect(area, luz)
        pintor.end()


class JanelaPrincipal(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.resize(1180, 780)
        self.setMinimumSize(940, 620)

        central = Fundo()
        esquema = QHBoxLayout(central)
        esquema.setContentsMargins(0, 0, 0, 0)
        esquema.setSpacing(0)

        self.paginas = QStackedWidget()
        self.paginas.setAttribute(Qt.WA_TranslucentBackground)
        esquema.addWidget(self._construir_lateral())
        esquema.addWidget(self.paginas, 1)
        self.setCentralWidget(central)

        self.pagina_diagnostico = PaginaDiagnostico()
        self.pagina_limpeza = PaginaLimpeza()
        self.pagina_arranque = PaginaArranque()
        self.pagina_otimizacoes = PaginaOtimizacoes()
        self.pagina_relatorio = PaginaRelatorio()

        for pagina in (
            self.pagina_diagnostico,
            self.pagina_limpeza,
            self.pagina_arranque,
            self.pagina_otimizacoes,
            self.pagina_relatorio,
        ):
            self.paginas.addWidget(pagina)

        # Tudo o que se faz nas outras páginas entra no relatório
        self.pagina_diagnostico.concluido.connect(self.pagina_relatorio.definir_diagnostico)
        self.pagina_limpeza.limpou.connect(self.pagina_relatorio.registar_acao)
        self.pagina_arranque.alterou.connect(self.pagina_relatorio.registar_acao)
        self.pagina_otimizacoes.alterou.connect(self.pagina_relatorio.registar_acao)

        self.botoes.buttons()[0].setChecked(True)
        self.paginas.setCurrentIndex(0)
        self._animacao: QPropertyAnimation | None = None
        self._movimento_reduzido = reduced_motion()

    def mostrar_pagina(self, indice: int) -> None:
        """Troca de página com um esbatimento curto, interrompível.

        A animação parte sempre da opacidade que está no ecrã, não de zero:
        clicar depressa entre separadores não provoca saltos.
        """
        if indice == self.paginas.currentIndex():
            return
        self.paginas.setCurrentIndex(indice)
        if self._movimento_reduzido:
            return

        pagina = self.paginas.currentWidget()
        efeito = pagina.graphicsEffect()
        if not isinstance(efeito, QGraphicsOpacityEffect):
            efeito = QGraphicsOpacityEffect(pagina)
            pagina.setGraphicsEffect(efeito)

        inicio = efeito.opacity() if self._animacao and self._animacao.state() else 0.0
        if self._animacao:
            self._animacao.stop()
        self._animacao = QPropertyAnimation(efeito, b"opacity", self)
        self._animacao.setDuration(theme.DURACAO_PAGINA)
        self._animacao.setStartValue(inicio)
        self._animacao.setEndValue(1.0)
        self._animacao.setEasingCurve(QEasingCurve.OutCubic)
        self._animacao.start()

    def _construir_lateral(self) -> QWidget:
        lateral = QWidget()
        lateral.setObjectName("lateral")
        lateral.setFixedWidth(228)
        esquema = QVBoxLayout(lateral)
        esquema.setContentsMargins(0, 0, 0, 0)
        esquema.setSpacing(0)

        chapa = QWidget()
        chapa.setObjectName("chapa")
        chapa_esquema = QVBoxLayout(chapa)
        chapa_esquema.setContentsMargins(18, 20, 18, 2)
        chapa_esquema.setSpacing(1)
        marca = QLabel(BRAND)
        marca.setObjectName("marca")
        chapa_esquema.addWidget(marca)
        esquema.addWidget(chapa)
        modelo = QLabel("OPTIMIZER")
        modelo.setObjectName("modelo")
        esquema.addWidget(modelo)

        self.botoes = QButtonGroup(self)
        self.botoes.setExclusive(True)
        entradas = [
            ("Diagnóstico", 0),
            ("Limpeza", 1),
            ("Arranque", 2),
            ("Otimizações", 3),
            ("Relatório", 4),
        ]
        for texto, indice in entradas:
            botao = QPushButton(texto)
            botao.setObjectName("nav")
            botao.setCheckable(True)
            botao.setCursor(Qt.PointingHandCursor)
            botao.clicked.connect(lambda _c, i=indice: self.mostrar_pagina(i))
            self.botoes.addButton(botao, indice)
            esquema.addWidget(botao)

        esquema.addStretch()

        separador = QFrame()
        separador.setObjectName("separadorLateral")
        separador.setFixedHeight(1)
        esquema.addWidget(separador)
        esquema.addWidget(self._etiqueta_servico())
        return lateral

    @staticmethod
    def _etiqueta_servico() -> QLabel:
        """Identifica a máquina que está na bancada.

        Um técnico trabalha em máquinas que não são suas — saber sempre em qual
        está a mexer vale mais do que repetir o nome da aplicação no rodapé.
        """
        if is_admin():
            privilegios = "privilégios: administrador"
        elif IS_WINDOWS:
            privilegios = "privilégios: limitados"
        else:
            privilegios = "privilégios: sob pedido"

        etiqueta = QLabel(
            f"MÁQUINA\n{socket.gethostname()[:26]}\n"
            f"{os_label()} · {platform.machine()}\n{privilegios}\nv{APP_VERSION}"
        )
        etiqueta.setObjectName("etiquetaServico")
        etiqueta.setWordWrap(True)
        return etiqueta


def run_gui() -> int:
    """Abre a janela. Devolve o código de saída do processo."""
    aplicacao = QApplication.instance() or QApplication(sys.argv)
    aplicacao.setApplicationName(APP_NAME)
    aplicacao.setOrganizationName(BRAND)
    aplicacao.setStyleSheet(theme.QSS)
    aplicacao.setFont(QFont(aplicacao.font().family(), 13 if IS_WINDOWS else 13))

    janela = JanelaPrincipal()
    janela.show()
    return aplicacao.exec()
