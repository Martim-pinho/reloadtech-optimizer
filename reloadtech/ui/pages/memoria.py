"""Página de memória: o que a ocupa e o que se pode mesmo fazer."""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...core import memoria
from ...platform_info import IS_WINDOWS, human_bytes, is_admin
from .. import theme
from ..gauges import MONO, UI, fonte
from ..widgets import Painel, titulo_pagina
from ..workers import Tarefa

# A repartição usa tons neutros de propósito: não é um veredicto, é uma
# descrição. A cor de estado fica reservada para quando há um problema.
TONS = ["#5ac8d8", "#4a8fa8", "#3d6b80", "#2c4a5a", "#243640"]


class BarraReparticao(QWidget):
    """Como a memória está repartida, em proporção real."""

    def __init__(self) -> None:
        super().__init__()
        self._partes: list[dict] = []
        self.setMinimumHeight(58)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def definir(self, partes: list[dict]) -> None:
        self._partes = partes
        self.update()

    def paintEvent(self, _evento) -> None:  # noqa: N802 - assinatura do Qt
        if not self._partes:
            return
        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.Antialiasing)
        largura = self.width()
        total = sum(parte["bytes"] for parte in self._partes) or 1

        topo, altura, x = 0.0, 14.0, 0.0
        pintor.setPen(Qt.NoPen)
        for indice, parte in enumerate(self._partes):
            fatia = largura * parte["bytes"] / total
            pintor.setBrush(QColor(TONS[indice % len(TONS)]))
            pintor.drawRect(QRectF(x, topo, max(fatia - 1.5, 0.0), altura))
            x += fatia

        # Legenda, na mesma ordem da barra
        y = topo + altura + 12
        x = 0.0
        for indice, parte in enumerate(self._partes):
            pintor.setBrush(QColor(TONS[indice % len(TONS)]))
            pintor.drawRect(QRectF(x, y + 3, 8, 8))
            pintor.setPen(QColor(theme.TINTA_SUAVE))
            pintor.setFont(fonte(UI, 9))
            texto = f"{parte['nome']}  "
            pintor.drawText(QRectF(x + 13, y, 200, 14), Qt.AlignLeft | Qt.AlignVCenter, texto)
            largura_nome = pintor.fontMetrics().horizontalAdvance(texto)
            pintor.setFont(fonte(MONO, 9, QFont.DemiBold))
            pintor.setPen(QColor(theme.TINTA))
            pintor.drawText(QRectF(x + 13 + largura_nome, y, 100, 14),
                            Qt.AlignLeft | Qt.AlignVCenter, parte["legivel"])
            x += 13 + largura_nome + pintor.fontMetrics().horizontalAdvance(parte["legivel"]) + 22
            pintor.setPen(Qt.NoPen)
        pintor.end()


class LinhaAcao(QFrame):
    """Uma operação de memória: o que faz, o que custa, e o botão."""

    executou = Signal(str)

    def __init__(self, acao: memoria.AcaoMemoria) -> None:
        super().__init__()
        self.acao = acao
        self._tarefa: Tarefa | None = None
        self.setObjectName("painel")

        esquema = QHBoxLayout(self)
        esquema.setContentsMargins(theme.MD + 2, theme.MD, theme.MD + 2, theme.MD)
        esquema.setSpacing(theme.MD)

        texto = QVBoxLayout()
        texto.setSpacing(3)
        titulo = QLabel(acao.nome)
        titulo.setStyleSheet("font-weight: 600; font-size: 13.5px; border: none;")
        descricao = QLabel(acao.descricao)
        descricao.setWordWrap(True)
        descricao.setStyleSheet(f"color: {theme.TINTA_SUAVE}; border: none;")
        custo = QLabel(acao.custo)
        custo.setWordWrap(True)
        custo.setStyleSheet(f"color: {theme.CAUTELA}; border: none; font-size: 12px;")
        texto.addWidget(titulo)
        texto.addWidget(descricao)
        texto.addWidget(custo)
        esquema.addLayout(texto, 1)

        self.botao = QPushButton("Executar")
        self.botao.setMinimumWidth(112)
        self.botao.clicked.connect(self._executar)
        if not acao.disponivel:
            self.botao.setEnabled(False)
            self.botao.setToolTip("Não é seguro executar neste momento")
        esquema.addWidget(self.botao, 0, Qt.AlignTop)

    def _executar(self) -> None:
        if self._tarefa and self._tarefa.isRunning():
            return
        resposta = QMessageBox.question(
            self, "Confirmar",
            f"{self.acao.nome}\n\n{self.acao.descricao}\n\n{self.acao.custo}\n\nExecutar?",
            QMessageBox.Cancel | QMessageBox.Yes, QMessageBox.Cancel,
        )
        if resposta != QMessageBox.Yes:
            return
        self.botao.setEnabled(False)
        self.botao.setText("A executar…")
        self._tarefa = Tarefa(memoria.executar_acao, self.acao, com_progresso=False)
        self._tarefa.terminado.connect(self._terminou)
        self._tarefa.falhou.connect(lambda erro: self._terminou((False, erro)))
        self._tarefa.start()

    def _terminou(self, resultado) -> None:
        ok, mensagem = resultado
        self.botao.setEnabled(self.acao.disponivel)
        self.botao.setText("Executar")
        if ok:
            self.executou.emit(f"Memória — {self.acao.nome}: {mensagem}")
            QMessageBox.information(self, "Concluído", mensagem)
        else:
            QMessageBox.critical(self, "Não foi possível concluir", mensagem)


class PaginaMemoria(QWidget):
    alterou = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._tarefa: Tarefa | None = None

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(theme.XL, theme.XL, theme.XL, theme.XL)
        raiz.setSpacing(theme.MD)

        topo = QHBoxLayout()
        topo.addWidget(titulo_pagina(
            "Memória",
            "Memória livre é memória desperdiçada: o sistema usa a que sobra como cache de "
            "disco, de propósito. O que resolve falta de RAM é fechar o que a ocupa.",
        ), 1)
        self.botao_atualizar = QPushButton("Atualizar")
        self.botao_atualizar.setObjectName("primario")
        self.botao_atualizar.clicked.connect(self.carregar)
        topo.addWidget(self.botao_atualizar, 0, Qt.AlignTop)
        raiz.addLayout(topo)

        area = QScrollArea()
        area.setWidgetResizable(True)
        conteudo = QWidget()
        esquema = QVBoxLayout(conteudo)
        esquema.setContentsMargins(0, 0, theme.SM, 0)
        esquema.setSpacing(theme.MD)
        area.setWidget(conteudo)
        raiz.addWidget(area, 1)

        # Repartição
        painel_reparticao = Painel("repartição")
        self.total = QLabel("—")
        self.total.setStyleSheet(
            f"font-family: {theme.FONTE_MONO}; font-size: 19px; font-weight: 700;")
        self.barra = BarraReparticao()
        painel_reparticao.corpo.addWidget(self.total)
        painel_reparticao.corpo.addWidget(self.barra)
        self.nota_swap = QLabel("")
        self.nota_swap.setObjectName("legenda")
        self.nota_swap.setWordWrap(True)
        painel_reparticao.corpo.addWidget(self.nota_swap)
        esquema.addWidget(painel_reparticao)

        # Consumidores
        painel_processos = Painel("o que está a ocupar a memória")
        self.arvore = QTreeWidget()
        self.arvore.setHeaderLabels(["PROGRAMA", "MEMÓRIA", "% DA RAM", "UTILIZADOR"])
        self.arvore.setRootIsDecorated(False)
        self.arvore.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.arvore.setFixedHeight(420)
        self.arvore.currentItemChanged.connect(self._selecao_mudou)
        painel_processos.corpo.addWidget(self.arvore)

        rodape = QHBoxLayout()
        self.detalhe = QLabel("Seleciona um programa para o poder fechar.")
        self.detalhe.setObjectName("legenda")
        rodape.addWidget(self.detalhe, 1)
        self.botao_fechar = QPushButton("Fechar programa")
        self.botao_fechar.setObjectName("perigo")
        self.botao_fechar.setEnabled(False)
        self.botao_fechar.clicked.connect(self._fechar)
        rodape.addWidget(self.botao_fechar)
        painel_processos.corpo.addLayout(rodape)
        esquema.addWidget(painel_processos)

        # Operações do sistema
        acoes = memoria.acoes_disponiveis()
        if acoes:
            rotulo = QLabel("OPERAÇÕES DE SISTEMA")
            rotulo.setObjectName("rotuloSeccao")
            esquema.addWidget(rotulo)
            if IS_WINDOWS and not is_admin() and any(a.requires_admin for a in acoes):
                aviso = QLabel("Algumas operações exigem abrir a aplicação como administrador.")
                aviso.setObjectName("avisoAdmin")
                aviso.setWordWrap(True)
                esquema.addWidget(aviso)
            for acao in acoes:
                linha = LinhaAcao(acao)
                linha.executou.connect(self.alterou.emit)
                esquema.addWidget(linha)

        esquema.addStretch()
        self.carregar()

    # --- Dados ---------------------------------------------------------------

    def carregar(self) -> None:
        if self._tarefa and self._tarefa.isRunning():
            return
        self.botao_atualizar.setEnabled(False)
        self._tarefa = Tarefa(self._recolher, com_progresso=False)
        self._tarefa.terminado.connect(self._mostrar)
        self._tarefa.falhou.connect(lambda erro: self.detalhe.setText(f"Falhou: {erro}"))
        self._tarefa.start()

    @staticmethod
    def _recolher() -> tuple[dict, list[memoria.Consumidor]]:
        return memoria.resumo(), memoria.consumidores(30)

    def _mostrar(self, dados) -> None:
        resumo, consumidores = dados
        self.botao_atualizar.setEnabled(True)

        cor = theme.cor_medicao(resumo["percentagem"])
        self.total.setText(f"{resumo['usada_legivel']} de {resumo['total_legivel']}")
        self.total.setStyleSheet(
            f"font-family: {theme.FONTE_MONO}; font-size: 19px; font-weight: 700; color: {cor};")
        self.barra.definir(resumo["reparticao"])

        if resumo["swap_total"]:
            self.nota_swap.setText(
                f"Swap em uso: {resumo['swap_legivel']} ({resumo['swap_percentagem']:.0f}%). "
                "Swap muito usada com a RAM cheia é o sinal de que falta memória a sério."
            )
        else:
            self.nota_swap.setText("Sem swap em uso.")

        self.arvore.clear()
        for consumidor in consumidores:
            item = QTreeWidgetItem([
                consumidor.nome, consumidor.memoria_legivel,
                f"{consumidor.percentagem}%", consumidor.utilizador,
            ])
            item.setData(0, Qt.UserRole, consumidor)
            if consumidor.protegido:
                item.setText(0, f"{consumidor.nome}  ⚠ sistema")
                item.setForeground(0, QColor(theme.TINTA_SUAVE))
            self.arvore.addTopLevelItem(item)

    def _selecao_mudou(self, atual: QTreeWidgetItem | None) -> None:
        if atual is None:
            self.botao_fechar.setEnabled(False)
            return
        consumidor: memoria.Consumidor = atual.data(0, Qt.UserRole)
        self.botao_fechar.setEnabled(not consumidor.protegido)
        if consumidor.protegido:
            self.detalhe.setText(f"{consumidor.nome} é um processo do sistema e não deve ser fechado.")
        else:
            self.detalhe.setText(
                f"{consumidor.nome} (pid {consumidor.pid}) — {consumidor.memoria_legivel} ocupados.")

    def _fechar(self) -> None:
        atual = self.arvore.currentItem()
        if atual is None:
            return
        consumidor: memoria.Consumidor = atual.data(0, Qt.UserRole)

        resposta = QMessageBox.question(
            self, "Fechar programa",
            f"Fechar «{consumidor.nome}»?\n\nLiberta {consumidor.memoria_legivel}. "
            "Trabalho não guardado nesse programa perde-se.",
            QMessageBox.Cancel | QMessageBox.Yes, QMessageBox.Cancel,
        )
        if resposta != QMessageBox.Yes:
            return

        ok, erro = memoria.terminar(consumidor)
        if ok:
            self.alterou.emit(
                f"Fechado «{consumidor.nome}», que ocupava {consumidor.memoria_legivel} de memória")
            self.carregar()
        else:
            QMessageBox.critical(self, "Não foi possível fechar", erro)
