"""Página de relatório: gera o documento que fica com o cliente."""
from __future__ import annotations

import subprocess
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ... import storage
from ...core import report
from ...platform_info import IS_MACOS, IS_WINDOWS
from .. import theme
from ..widgets import Painel, titulo_pagina


class PaginaRelatorio(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.snapshot: dict = {}
        self.acoes: list[str] = []

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(28, 24, 28, 24)
        raiz.setSpacing(16)

        raiz.addWidget(titulo_pagina(
            "Relatório para o cliente",
            "Gera um documento com o diagnóstico e o trabalho feito, pronto a entregar.",
        ))

        dados = Painel("Identificação")
        self.cliente = QLineEdit()
        self.cliente.setPlaceholderText("Nome do cliente ou da empresa")
        self.tecnico = QLineEdit()
        self.tecnico.setPlaceholderText("Técnico responsável")
        for rotulo, campo in (("Cliente", self.cliente), ("Técnico", self.tecnico)):
            linha = QHBoxLayout()
            etiqueta = QLabel(rotulo)
            etiqueta.setMinimumWidth(80)
            etiqueta.setStyleSheet(f"color: {theme.TINTA_SUAVE};")
            linha.addWidget(etiqueta)
            linha.addWidget(campo, 1)
            dados.corpo.addLayout(linha)

        self.notas = QTextEdit()
        self.notas.setPlaceholderText(
            "Observações a incluir no relatório: peças substituídas, "
            "recomendações ao cliente, trabalho pendente…"
        )
        self.notas.setFixedHeight(90)
        dados.corpo.addWidget(self.notas)
        raiz.addWidget(dados)

        self.cartao_acoes = Painel("Intervenções registadas nesta sessão")
        self.lista_acoes = QListWidget()
        self.lista_acoes.setFixedHeight(120)
        self.cartao_acoes.corpo.addWidget(self.lista_acoes)
        nota = QLabel("Preenchida automaticamente à medida que limpas, desativas arranques "
                      "ou aplicas otimizações.")
        nota.setObjectName("legenda")
        nota.setWordWrap(True)
        self.cartao_acoes.corpo.addWidget(nota)
        raiz.addWidget(self.cartao_acoes)

        self.aviso = QLabel("Corre primeiro o diagnóstico — sem ele o relatório fica sem dados.")
        self.aviso.setObjectName("avisoAdmin")
        self.aviso.setWordWrap(True)
        raiz.addWidget(self.aviso)

        raiz.addStretch()

        botoes = QHBoxLayout()
        self.botao_pasta = QPushButton("Abrir pasta de relatórios")
        self.botao_pasta.setObjectName("secundario")
        self.botao_pasta.clicked.connect(self._abrir_pasta)
        self.botao_html = QPushButton("Gerar HTML")
        self.botao_html.setObjectName("secundario")
        self.botao_html.clicked.connect(lambda: self._gerar("html"))
        self.botao_pdf = QPushButton("Gerar PDF")
        self.botao_pdf.clicked.connect(lambda: self._gerar("pdf"))
        botoes.addWidget(self.botao_pasta)
        botoes.addStretch()
        botoes.addWidget(self.botao_html)
        botoes.addWidget(self.botao_pdf)
        raiz.addLayout(botoes)

        self._atualizar_disponibilidade()

    # --- Estado --------------------------------------------------------------

    def definir_diagnostico(self, snapshot: dict) -> None:
        self.snapshot = snapshot
        self._atualizar_disponibilidade()

    def registar_acao(self, texto: str) -> None:
        self.acoes.append(texto)
        self.lista_acoes.addItem(texto)

    def _atualizar_disponibilidade(self) -> None:
        tem = bool(self.snapshot)
        self.botao_html.setEnabled(tem)
        self.botao_pdf.setEnabled(tem)
        self.aviso.setVisible(not tem)

    # --- Geração -------------------------------------------------------------

    def _contexto(self) -> dict:
        return {
            "cliente": self.cliente.text().strip() or "—",
            "tecnico": self.tecnico.text().strip() or "—",
            "notas": self.notas.toPlainText().strip(),
            "acoes": self.acoes,
        }

    def _gerar(self, formato: str) -> None:
        if not self.snapshot:
            return
        sugestao = storage.reports_dir() / (
            f"relatorio-{(self.cliente.text().strip() or 'cliente').replace(' ', '-').lower()}.{formato}"
        )
        caminho, _ = QFileDialog.getSaveFileName(
            self, "Guardar relatório", str(sugestao),
            "Documento PDF (*.pdf)" if formato == "pdf" else "Página HTML (*.html)",
        )
        if not caminho:
            return
        try:
            if formato == "pdf":
                destino = report.save_pdf(self.snapshot, self._contexto(), Path(caminho))
            else:
                destino = report.save_html(self.snapshot, self._contexto(), Path(caminho))
        except ImportError:
            QMessageBox.critical(
                self, "PDF indisponível",
                "A geração de PDF precisa da biblioteca reportlab.\n\n"
                "Instala com:  pip install reportlab",
            )
            return
        except OSError as exc:
            QMessageBox.critical(self, "Não foi possível guardar", str(exc))
            return

        resposta = QMessageBox.question(
            self, "Relatório criado", f"Guardado em:\n{destino}\n\nAbrir agora?",
            QMessageBox.No | QMessageBox.Yes, QMessageBox.Yes,
        )
        if resposta == QMessageBox.Yes:
            self._abrir(destino)

    @staticmethod
    def _abrir(caminho: Path) -> None:
        if IS_WINDOWS:
            subprocess.Popen(["cmd", "/c", "start", "", str(caminho)], shell=False)
        elif IS_MACOS:
            subprocess.Popen(["open", str(caminho)])
        else:
            subprocess.Popen(["xdg-open", str(caminho)])

    def _abrir_pasta(self) -> None:
        self._abrir(storage.reports_dir())
