"""Página de programas instalados: onde está o espaço a sério."""
from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...core import programas
from ...platform_info import IS_MACOS, human_bytes
from .. import theme
from ..widgets import titulo_pagina
from ..workers import Tarefa

MESES_SEM_USO = 6


class PaginaProgramas(QWidget):
    alterou = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._programas: list[programas.Programa] = []
        self._tarefa: Tarefa | None = None

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(theme.XL, theme.XL, theme.XL, theme.XL)
        raiz.setSpacing(theme.MD)

        topo = QHBoxLayout()
        topo.addWidget(titulo_pagina(
            "Programas instalados",
            "Limpar caches devolve alguns GB. Remover programas que ninguém abre há meses "
            "devolve dezenas.",
        ), 1)
        self.botao_atualizar = QPushButton("Atualizar")
        self.botao_atualizar.setObjectName("primario")
        self.botao_atualizar.clicked.connect(self.carregar)
        topo.addWidget(self.botao_atualizar, 0, Qt.AlignTop)
        raiz.addLayout(topo)

        filtros = QHBoxLayout()
        filtros.setSpacing(theme.LG)
        self.procura = QLineEdit()
        self.procura.setPlaceholderText("Procurar por nome…")
        self.procura.textChanged.connect(self._aplicar_filtros)
        filtros.addWidget(self.procura, 1)

        self.so_esquecidos = QCheckBox(f"Só os que não são abertos há {MESES_SEM_USO} meses")
        self.so_esquecidos.setEnabled(IS_MACOS)
        if not IS_MACOS:
            self.so_esquecidos.setToolTip("Este sistema não regista a data do último uso")
        self.so_esquecidos.stateChanged.connect(self._aplicar_filtros)
        filtros.addWidget(self.so_esquecidos)

        self.esconder_sistema = QCheckBox("Esconder os do sistema")
        self.esconder_sistema.setChecked(True)
        self.esconder_sistema.stateChanged.connect(self._aplicar_filtros)
        filtros.addWidget(self.esconder_sistema)
        raiz.addLayout(filtros)

        self.arvore = QTreeWidget()
        self.arvore.setHeaderLabels(["PROGRAMA", "TAMANHO", "VERSÃO", "ÚLTIMO USO", "EDITOR"])
        self.arvore.setRootIsDecorated(False)
        self.arvore.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.arvore.setColumnWidth(1, 100)
        self.arvore.setSortingEnabled(False)
        self.arvore.currentItemChanged.connect(self._selecao_mudou)
        raiz.addWidget(self.arvore, 1)

        self.detalhe = QLabel("Seleciona um programa para ver os detalhes.")
        self.detalhe.setObjectName("legenda")
        self.detalhe.setWordWrap(True)
        raiz.addWidget(self.detalhe)

        rodape = QHBoxLayout()
        self.resumo = QLabel("")
        rodape.addWidget(self.resumo, 1)
        self.botao_remover = QPushButton("Desinstalar")
        self.botao_remover.setObjectName("perigo")
        self.botao_remover.setEnabled(False)
        self.botao_remover.clicked.connect(self._remover)
        rodape.addWidget(self.botao_remover)
        raiz.addLayout(rodape)

        self.carregar()

    # --- Dados ---------------------------------------------------------------

    def carregar(self) -> None:
        if self._tarefa and self._tarefa.isRunning():
            return
        self.botao_atualizar.setEnabled(False)
        self.resumo.setText("A ler a lista de programas…")
        self._tarefa = Tarefa(programas.listar)
        self._tarefa.terminado.connect(self._recebido)
        self._tarefa.falhou.connect(lambda erro: self.resumo.setText(f"Falhou: {erro}"))
        self._tarefa.start()

    def _recebido(self, lista: list[programas.Programa]) -> None:
        self._programas = lista
        self.botao_atualizar.setEnabled(True)
        self._aplicar_filtros()

    def _meses_sem_uso(self, programa: programas.Programa) -> int | None:
        if not programa.ultimo_uso:
            return None
        try:
            usado = datetime.strptime(programa.ultimo_uso, "%d/%m/%Y")
        except ValueError:
            return None
        return (datetime.now() - usado).days // 30

    def _aplicar_filtros(self) -> None:
        texto = self.procura.text().strip().lower()
        visiveis: list[programas.Programa] = []

        for programa in self._programas:
            if self.esconder_sistema.isChecked() and programa.do_sistema:
                continue
            if texto and texto not in programa.nome.lower():
                continue
            if self.so_esquecidos.isChecked():
                meses = self._meses_sem_uso(programa)
                if meses is None or meses < MESES_SEM_USO:
                    continue
            visiveis.append(programa)

        self.arvore.clear()
        for programa in visiveis:
            meses = self._meses_sem_uso(programa)
            uso = programa.ultimo_uso or "—"
            if meses is not None and meses >= MESES_SEM_USO:
                uso = f"{uso}  ({meses} meses)"

            item = QTreeWidgetItem([
                programa.nome, programa.tamanho_legivel, programa.versao or "—",
                uso, programa.editor or "—",
            ])
            item.setData(0, Qt.UserRole, programa)
            if programa.do_sistema:
                item.setForeground(0, QColor(theme.TINTA_SUAVE))
            if meses is not None and meses >= MESES_SEM_USO:
                item.setForeground(3, QColor(theme.CAUTELA))
            self.arvore.addTopLevelItem(item)

        total = programas.espaco_total(visiveis)
        esquecidos = [p for p in visiveis
                      if (m := self._meses_sem_uso(p)) is not None and m >= MESES_SEM_USO]
        mensagem = f"{len(visiveis)} programas · {human_bytes(total)} ocupados"
        if esquecidos:
            mensagem += (f"   <span style='color:{theme.CAUTELA}'>"
                         f"{len(esquecidos)} sem uso há meses, "
                         f"{human_bytes(programas.espaco_total(esquecidos))} recuperáveis</span>")
        self.resumo.setText(mensagem)
        self.resumo.setTextFormat(Qt.RichText)

    def _selecao_mudou(self, atual: QTreeWidgetItem | None) -> None:
        if atual is None:
            self.botao_remover.setEnabled(False)
            return
        programa: programas.Programa = atual.data(0, Qt.UserRole)
        pode, motivo = programas.pode_remover(programa)
        self.botao_remover.setEnabled(pode)
        if pode:
            local = programa.localizacao or programa.identificador
            self.detalhe.setText(f"{programa.nome} — {programa.tamanho_legivel}   {local}")
        else:
            self.detalhe.setText(f"{programa.nome} — {motivo}")

    def _remover(self) -> None:
        atual = self.arvore.currentItem()
        if atual is None:
            return
        programa: programas.Programa = atual.data(0, Qt.UserRole)

        destino = ("O programa vai para o Lixo, portanto dá para recuperar."
                   if IS_MACOS else
                   "Vai correr o desinstalador do programa, que pode abrir uma janela própria.")
        resposta = QMessageBox.question(
            self, "Desinstalar",
            f"Desinstalar «{programa.nome}»?\n\nLiberta {programa.tamanho_legivel}.\n{destino}\n\n"
            "Os documentos criados com o programa não são afetados.",
            QMessageBox.Cancel | QMessageBox.Yes, QMessageBox.Cancel,
        )
        if resposta != QMessageBox.Yes:
            return

        self.botao_remover.setEnabled(False)
        self.botao_remover.setText("A desinstalar…")
        self._tarefa = Tarefa(programas.remover, programa, com_progresso=False)
        self._tarefa.terminado.connect(lambda r: self._removido(r, programa))
        self._tarefa.falhou.connect(lambda erro: self._removido((False, erro), programa))
        self._tarefa.start()

    def _removido(self, resultado, programa: programas.Programa) -> None:
        ok, erro = resultado
        self.botao_remover.setText("Desinstalar")
        if ok:
            self.alterou.emit(
                f"Desinstalado «{programa.nome}», libertando {programa.tamanho_legivel}")
            self.carregar()
        else:
            self.botao_remover.setEnabled(True)
            QMessageBox.critical(self, "Não foi possível desinstalar",
                                 erro or "O desinstalador falhou.")
