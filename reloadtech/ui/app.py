"""Janela principal e arranque da interface gráfica."""
from __future__ import annotations

import platform
import socket
import sys

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QSize, Qt
from PySide6.QtGui import QFont, QFontDatabase
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
from . import icons, theme
from .pages.arranque import PaginaArranque
from .pages.diagnostico import PaginaDiagnostico
from .pages.limpeza import PaginaLimpeza
from .pages.otimizacoes import PaginaOtimizacoes
from .pages.relatorio import PaginaRelatorio

SECCOES = [
    ("Diagnóstico", "diagnostico"),
    ("Limpeza", "limpeza"),
    ("Arranque", "arranque"),
    ("Otimizações", "otimizacoes"),
    ("Relatório", "relatorio"),
]


def carregar_fontes() -> None:
    """Regista as fontes incluídas no pacote.

    Sem isto o Qt cai na primeira família instalada que encontre — no macOS,
    Helvetica Neue — e a aplicação ganha um ar de software de há vinte anos.
    """
    if not theme.PASTA_FONTES.is_dir():
        return
    for ficheiro in sorted(theme.PASTA_FONTES.glob("*.ttf")):
        QFontDatabase.addApplicationFont(str(ficheiro))


class JanelaPrincipal(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.resize(1220, 820)
        self.setMinimumSize(980, 660)

        central = QWidget()
        # Por objectName, não por setStyleSheet: uma folha de estilo aplicada a
        # um widget cascateia para todos os filhos e sobrepõe-se à da aplicação
        # — era o que apagava o fundo do botão principal.
        central.setObjectName("fundoJanela")
        esquema = QHBoxLayout(central)
        esquema.setContentsMargins(0, 0, 0, 0)
        esquema.setSpacing(0)

        self.paginas = QStackedWidget()
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
        self.pagina_diagnostico.concluido.connect(self._atualizar_cartao)
        self.pagina_limpeza.limpou.connect(self.pagina_relatorio.registar_acao)
        self.pagina_arranque.alterou.connect(self.pagina_relatorio.registar_acao)
        self.pagina_otimizacoes.alterou.connect(self.pagina_relatorio.registar_acao)

        self.botoes.buttons()[0].setChecked(True)
        self.paginas.setCurrentIndex(0)
        self._animacao: QPropertyAnimation | None = None
        self._movimento_reduzido = reduced_motion()

    # --- Navegação -----------------------------------------------------------

    def mostrar_pagina(self, indice: int) -> None:
        """Troca de página com um esbatimento curto e interrompível.

        A animação parte da opacidade que está no ecrã, não de zero: clicar
        depressa entre separadores não provoca saltos.
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

    # --- Barra lateral -------------------------------------------------------

    def _construir_lateral(self) -> QWidget:
        lateral = QWidget()
        lateral.setObjectName("lateral")
        lateral.setFixedWidth(214)
        esquema = QVBoxLayout(lateral)
        esquema.setContentsMargins(0, 0, 0, 0)
        esquema.setSpacing(0)

        chapa = QWidget()
        chapa_esquema = QVBoxLayout(chapa)
        chapa_esquema.setContentsMargins(theme.LG, theme.XL, theme.LG, theme.XL)
        chapa_esquema.setSpacing(2)
        marca = QLabel(BRAND)
        marca.setObjectName("marca")
        modelo = QLabel("OPTIMIZER")
        modelo.setObjectName("modelo")
        chapa_esquema.addWidget(marca)
        chapa_esquema.addWidget(modelo)
        esquema.addWidget(chapa)

        self.botoes = QButtonGroup(self)
        self.botoes.setExclusive(True)
        for indice, (texto, icone) in enumerate(SECCOES):
            botao = QPushButton(texto)
            botao.setObjectName("nav")
            botao.setCheckable(True)
            botao.setCursor(Qt.PointingHandCursor)
            botao.setIcon(icons.icone(icone, theme.TINTA_SUAVE, theme.TINTA))
            botao.setIconSize(QSize(17, 17))
            botao.clicked.connect(lambda _c, i=indice: self.mostrar_pagina(i))
            self.botoes.addButton(botao, indice)
            esquema.addWidget(botao)

        esquema.addStretch()
        esquema.addWidget(self._cartao_maquina())
        return lateral

    def _cartao_maquina(self) -> QWidget:
        """Identifica a máquina em intervenção.

        Um técnico trabalha em computadores que não são seus. Saber sempre em
        qual está a mexer vale mais do que repetir o nome da aplicação.
        """
        envolvente = QWidget()
        fora = QVBoxLayout(envolvente)
        fora.setContentsMargins(theme.MD, 0, theme.MD, theme.MD)

        cartao = QFrame()
        cartao.setObjectName("cartaoMaquina")
        dentro = QVBoxLayout(cartao)
        dentro.setContentsMargins(theme.MD, 11, theme.MD, 12)
        dentro.setSpacing(3)

        rotulo = QLabel("EM INTERVENÇÃO")
        rotulo.setObjectName("maquinaRotulo")
        nome = QLabel(socket.gethostname().split(".")[0][:22])
        nome.setObjectName("maquinaNome")

        if is_admin():
            privilegios = "administrador"
        elif IS_WINDOWS:
            privilegios = "sem privilégios"
        else:
            privilegios = "eleva sob pedido"
        detalhe = QLabel(f"{os_label()} · {platform.machine()}\n{privilegios}")
        detalhe.setObjectName("maquinaDetalhe")

        self.estado_maquina = QLabel("por analisar")
        self.estado_maquina.setObjectName("maquinaDetalhe")

        dentro.addWidget(rotulo)
        dentro.addWidget(nome)
        dentro.addWidget(detalhe)
        dentro.addWidget(self.estado_maquina)
        fora.addWidget(cartao)
        return envolvente

    def _atualizar_cartao(self, snapshot: dict) -> None:
        """Depois de analisar, o cartão passa a mostrar o veredicto."""
        pontuacao = snapshot.get("pontuacao", 0)
        cor = theme.cor_medicao(pontuacao, invertido=True)
        self.estado_maquina.setText(f"saúde {pontuacao}/100")
        self.estado_maquina.setStyleSheet(
            f"color: {cor}; font-family: {theme.FONTE_MONO}; font-size: 10px; font-weight: 600;")


def run_gui() -> int:
    """Abre a janela. Devolve o código de saída do processo."""
    aplicacao = QApplication.instance() or QApplication(sys.argv)
    aplicacao.setApplicationName(APP_NAME)
    aplicacao.setOrganizationName(BRAND)

    carregar_fontes()
    base = QFont(theme.FAMILIA_UI, 13)
    base.setStyleStrategy(QFont.PreferAntialias)
    aplicacao.setFont(base)
    aplicacao.setStyleSheet(theme.QSS)

    janela = JanelaPrincipal()
    janela.show()
    return aplicacao.exec()
