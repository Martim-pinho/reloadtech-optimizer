"""Página de arranque: o que corre quando o sistema liga."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...core import startup
from ...platform_info import IS_WINDOWS, is_admin
from .. import theme
from ..widgets import titulo_pagina
from ..workers import Tarefa


class PaginaArranque(QWidget):
    alterou = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._tarefa: Tarefa | None = None

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(theme.XL, theme.XL, theme.XL, theme.XL)
        raiz.setSpacing(theme.MD)

        topo = QHBoxLayout()
        topo.addWidget(titulo_pagina(
            "Arranque do sistema",
            "Quanto mais programas arrancam com o sistema, mais lento fica o arranque. "
            "Desativar é sempre reversível — nada é apagado.",
        ), 1)
        self.botao_atualizar = QPushButton("Atualizar lista")
        self.botao_atualizar.setObjectName("secundario")
        self.botao_atualizar.clicked.connect(self.carregar)
        topo.addWidget(self.botao_atualizar, 0, Qt.AlignTop)
        raiz.addLayout(topo)

        if IS_WINDOWS and not is_admin():
            aviso = QLabel(
                "Alguns itens são do sistema e só podem ser alterados se abrires "
                "a aplicação como administrador."
            )
            aviso.setObjectName("avisoAdmin")
            aviso.setWordWrap(True)
            raiz.addWidget(aviso)

        self.arvore = QTreeWidget()
        self.arvore.setHeaderLabels(["Estado", "Nome", "Origem", "Âmbito"])
        self.arvore.setRootIsDecorated(False)
        self.arvore.setAlternatingRowColors(True)
        self.arvore.header().setSectionResizeMode(1, QHeaderView.Stretch)
        self.arvore.setColumnWidth(0, 100)
        self.arvore.currentItemChanged.connect(self._selecao_mudou)
        raiz.addWidget(self.arvore, 1)

        self.detalhe = QLabel("Seleciona uma entrada para ver o comando que executa.")
        self.detalhe.setObjectName("legenda")
        self.detalhe.setWordWrap(True)
        self.detalhe.setTextInteractionFlags(Qt.TextSelectableByMouse)
        raiz.addWidget(self.detalhe)

        rodape = QHBoxLayout()
        self.resumo = QLabel("")
        rodape.addWidget(self.resumo, 1)
        self.botao_alternar = QPushButton("Desativar")
        self.botao_alternar.clicked.connect(self._alternar)
        self.botao_alternar.setEnabled(False)
        rodape.addWidget(self.botao_alternar)
        raiz.addLayout(rodape)

        self.carregar()

    def carregar(self) -> None:
        self.botao_atualizar.setEnabled(False)
        self.arvore.clear()
        self._tarefa = Tarefa(startup.list_items, com_progresso=False)
        self._tarefa.terminado.connect(self._mostrar)
        self._tarefa.falhou.connect(lambda erro: self.resumo.setText(f"Falhou: {erro}"))
        self._tarefa.start()

    def _mostrar(self, itens: list[startup.StartupItem]) -> None:
        self.botao_atualizar.setEnabled(True)
        self.arvore.clear()
        for item in itens:
            no = QTreeWidgetItem([
                "Ativo" if item.ativo else "Desativado",
                item.nome,
                item.origem,
                "Todos os utilizadores" if item.escopo == "sistema" else "Este utilizador",
            ])
            no.setData(0, Qt.UserRole, item)
            if not item.ativo:
                no.setForeground(0, Qt.GlobalColor.gray)
                no.setForeground(1, Qt.GlobalColor.gray)
            if startup.is_protected(item):
                no.setText(1, f"{item.nome}  ⚠ essencial")
                no.setForeground(1, Qt.GlobalColor.darkYellow)
            self.arvore.addTopLevelItem(no)

        ativos = sum(1 for i in itens if i.ativo)
        aviso = ""
        if ativos > 12:
            aviso = f"  <span style='color:{theme.FALHA}'>— são muitos, o arranque vai sentir isso</span>"
        self.resumo.setText(f"{ativos} ativos de {len(itens)} entradas{aviso}")
        self.resumo.setTextFormat(Qt.RichText)

    def _selecao_mudou(self, atual: QTreeWidgetItem | None) -> None:
        if atual is None:
            self.botao_alternar.setEnabled(False)
            return
        item: startup.StartupItem = atual.data(0, Qt.UserRole)
        self.botao_alternar.setEnabled(True)
        self.botao_alternar.setText("Ativar" if not item.ativo else "Desativar")
        self.botao_alternar.setObjectName("secundario" if item.ativo else "")
        self.detalhe.setText(item.comando or item.origem)

    def _alternar(self) -> None:
        atual = self.arvore.currentItem()
        if atual is None:
            return
        item: startup.StartupItem = atual.data(0, Qt.UserRole)
        ativar = not item.ativo

        if not ativar and startup.is_protected(item):
            QMessageBox.warning(
                self, "Serviço essencial",
                f"«{item.nome}» é um serviço essencial. Desativá-lo pode deixar a máquina "
                "sem rede ou sem acesso remoto.\n\nA ferramenta não permite desativá-lo.",
            )
            return

        if not ativar:
            resposta = QMessageBox.question(
                self, "Desativar arranque",
                f"Desativar «{item.nome}»?\n\nO programa continua instalado — apenas deixa de "
                "arrancar sozinho. Podes reverter aqui a qualquer momento.",
                QMessageBox.Cancel | QMessageBox.Yes, QMessageBox.Cancel,
            )
            if resposta != QMessageBox.Yes:
                return

        ok, erro = startup.set_enabled(item, ativar)
        if ok:
            self.alterou.emit(
                f"{'Ativado' if ativar else 'Desativado'} no arranque: {item.nome}")
            self.carregar()
        else:
            QMessageBox.critical(self, "Não foi possível alterar", erro or "Operação falhou.")
