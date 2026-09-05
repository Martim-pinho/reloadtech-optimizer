"""Página de diagnóstico: recolhe e apresenta o estado da máquina."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...core import diagnostics, startup
from .. import theme
from ..gauges import EscalaSaude, Medidor
from ..widgets import Painel, Conclusao, linha_dados, titulo_pagina
from ..workers import Tarefa


class PaginaDiagnostico(QWidget):
    concluido = Signal(dict)

    def __init__(self) -> None:
        super().__init__()
        self.snapshot: dict = {}
        self._tarefa: Tarefa | None = None
        self._medidores_volume: list[Medidor] = []

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(26, 22, 26, 22)
        raiz.setSpacing(14)

        topo = QHBoxLayout()
        topo.addWidget(titulo_pagina(
            "Diagnóstico",
            "Leitura do estado da máquina. Esta análise não altera nada no sistema.",
        ), 1)
        self.botao = QPushButton("Analisar sistema")
        self.botao.clicked.connect(self.analisar)
        topo.addWidget(self.botao, 0, Qt.AlignTop)
        raiz.addLayout(topo)

        self.barra = QProgressBar()
        self.barra.setTextVisible(False)
        self.barra.hide()
        self.estado = QLabel("Nenhuma análise feita nesta sessão.")
        self.estado.setObjectName("leitura")
        self.estado.setStyleSheet(f"color: {theme.TINTA_SUAVE}; font-size: 11px;")
        raiz.addWidget(self.barra)
        raiz.addWidget(self.estado)

        area = QScrollArea()
        area.setWidgetResizable(True)
        self.conteudo = QWidget()
        self.esquema = QVBoxLayout(self.conteudo)
        self.esquema.setContentsMargins(0, 0, 8, 0)
        self.esquema.setSpacing(14)
        area.setWidget(self.conteudo)
        raiz.addWidget(area, 1)

        self._montar_leituras()
        self.esquema.addStretch()

    def _montar_leituras(self) -> None:
        """Painel de leituras: a escala de saúde e os medidores calibrados."""
        painel = Painel("leituras")
        self.escala = EscalaSaude()
        painel.corpo.addWidget(self.escala)

        grelha = QWidget()
        grelha.setStyleSheet("background: transparent;")
        self.grelha_medidores = QGridLayout(grelha)
        self.grelha_medidores.setContentsMargins(0, 6, 0, 0)
        self.grelha_medidores.setHorizontalSpacing(26)
        self.grelha_medidores.setVerticalSpacing(10)

        self.medidor_cpu = Medidor("processador")
        self.medidor_memoria = Medidor("memória")
        self.grelha_medidores.addWidget(self.medidor_cpu, 0, 0)
        self.grelha_medidores.addWidget(self.medidor_memoria, 0, 1)
        painel.corpo.addWidget(grelha)

        nota = QLabel("A linha a tracejado marca o limiar a partir do qual o valor "
                      "passa a merecer atenção.")
        nota.setObjectName("legenda")
        nota.setWordWrap(True)
        nota.setStyleSheet(f"color: {theme.TINTA_SUAVE}; font-size: 11px;")
        painel.corpo.addWidget(nota)
        self.esquema.addWidget(painel)

    # --- Execução ------------------------------------------------------------

    def analisar(self) -> None:
        if self._tarefa and self._tarefa.isRunning():
            return
        self.botao.setEnabled(False)
        self.botao.setText("A analisar…")
        self.barra.setValue(0)
        self.barra.show()

        self._tarefa = Tarefa(self._recolher)
        self._tarefa.progresso.connect(self._progresso)
        self._tarefa.terminado.connect(self._mostrar)
        self._tarefa.falhou.connect(self._erro)
        self._tarefa.start()

    @staticmethod
    def _recolher(progress=None) -> dict:
        snapshot = diagnostics.collect(progress=progress)
        snapshot["arranque_total"] = len([i for i in startup.list_items() if i.ativo])
        snapshot["conclusoes"] = diagnostics.build_findings(snapshot)
        snapshot["pontuacao"] = diagnostics.health_score(snapshot)
        return snapshot

    def _progresso(self, pct: int, texto: str) -> None:
        self.barra.setValue(pct)
        self.estado.setText(texto)

    def _erro(self, mensagem: str) -> None:
        self.botao.setEnabled(True)
        self.botao.setText("Analisar sistema")
        self.barra.hide()
        self.estado.setText(f"A análise falhou: {mensagem}")

    def _mostrar(self, snapshot: dict) -> None:
        self.snapshot = snapshot
        self.botao.setEnabled(True)
        self.botao.setText("Analisar de novo")
        self.barra.hide()
        self.estado.setText(f"Análise de {snapshot.get('gerado_em', '')}")

        # Limpa tudo abaixo do painel de leituras
        while self.esquema.count() > 1:
            item = self.esquema.takeAt(1)
            if item.widget():
                item.widget().deleteLater()

        self.escala.definir(snapshot["pontuacao"])

        cpu = snapshot["cpu"]
        self.medidor_cpu.definir(cpu["utilizacao_pct"], f"{cpu['utilizacao_pct']:.0f}%",
                                 str(cpu["modelo"])[:44])
        memoria = snapshot["memoria"]
        self.medidor_memoria.definir(
            memoria["utilizacao_pct"], f"{memoria['utilizacao_pct']:.0f}%",
            f"{memoria['usada_legivel']} em uso de {memoria['total_legivel']}")

        # Um medidor por volume, criados conforme a máquina
        for medidor in self._medidores_volume:
            self.grelha_medidores.removeWidget(medidor)
            medidor.deleteLater()
        self._medidores_volume = []
        for indice, particao in enumerate(snapshot["particoes"][:4]):
            medidor = Medidor(particao.get("nome", particao["ponto_montagem"])[:26])
            medidor.definir(particao["utilizacao_pct"], f"{particao['utilizacao_pct']:.0f}%",
                            f"{particao['livre_legivel']} livres de {particao['total_legivel']}")
            self.grelha_medidores.addWidget(medidor, 1 + indice // 2, indice % 2)
            self._medidores_volume.append(medidor)

        # Conclusões
        conclusoes = Painel("conclusões")
        for item in snapshot["conclusoes"]:
            conclusoes.corpo.addWidget(Conclusao(item))
        self.esquema.addWidget(conclusoes)

        # Ficha técnica
        sistema = snapshot["sistema"]
        ficha = Painel("ficha técnica")
        dados = [
            ("Sistema operativo", sistema.get("sistema"), False),
            ("Equipamento", sistema.get("modelo"), False),
            ("Número de série", sistema.get("numero_serie"), True),
            ("Nome na rede", sistema.get("hostname"), True),
            ("Processador", cpu.get("modelo"), False),
            ("Núcleos", f"{cpu.get('nucleos_fisicos')} físicos · {cpu.get('nucleos_logicos')} lógicos", True),
            ("Memória instalada", memoria.get("total_legivel"), True),
            ("Placa gráfica", ", ".join(snapshot.get("gpu", [])) or "n/d", False),
            ("Ligado desde", f"{sistema.get('arranque')} · há {sistema.get('tempo_ligado')}", True),
        ]
        if sistema.get("carga_media"):
            dados.append(("Carga média", sistema["carga_media"], True))
        bateria = snapshot.get("bateria")
        if bateria:
            dados.append(("Bateria", f"{bateria['percentagem']}% · {bateria['saude']} "
                                     f"· {bateria['ciclos']} ciclos", True))
        for rotulo, valor, mono in dados:
            ficha.corpo.addWidget(linha_dados(rotulo, valor if valor is not None else "n/d", mono))
        self.esquema.addWidget(ficha)

        # Estado dos discos
        discos = snapshot.get("discos_fisicos", [])
        if discos:
            saude_painel = Painel("estado dos discos")
            saude = QTreeWidget()
            saude.setHeaderLabels(["DISCO", "TIPO", "CAPACIDADE", "SMART"])
            saude.setRootIsDecorated(False)
            saude.setAlternatingRowColors(True)
            for disco in discos:
                item = QTreeWidgetItem([disco["nome"], disco["tipo"], disco["capacidade"], disco["saude"]])
                item.setForeground(
                    3, Qt.GlobalColor.darkGreen if disco["saude"] == "Saudável" else Qt.GlobalColor.red)
                saude.addTopLevelItem(item)
            saude.header().setSectionResizeMode(0, QHeaderView.Stretch)
            saude.setFixedHeight(34 + 30 * len(discos))
            saude_painel.corpo.addWidget(saude)
            self.esquema.addWidget(saude_painel)

        # Processos
        processos = snapshot.get("processos", [])
        painel_processos = Painel("programas com maior consumo")
        tabela = QTreeWidget()
        tabela.setHeaderLabels(["PROGRAMA", "PID", "CPU", "MEMÓRIA"])
        tabela.setRootIsDecorated(False)
        tabela.setAlternatingRowColors(True)
        for proc in processos:
            tabela.addTopLevelItem(QTreeWidgetItem(
                [proc["nome"], str(proc["pid"]), f"{proc['cpu_pct']}%", proc["memoria_legivel"]]
            ))
        tabela.header().setSectionResizeMode(0, QHeaderView.Stretch)
        tabela.setFixedHeight(34 + 30 * max(1, len(processos)))
        painel_processos.corpo.addWidget(tabela)
        self.esquema.addWidget(painel_processos)

        self.esquema.addStretch()
        self.concluido.emit(snapshot)
