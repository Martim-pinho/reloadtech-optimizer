"""Identidade visual: instrumento de bancada, registo escuro.

Três regras governam tudo:

1. **A cor significa o estado de uma medição.** Verde, âmbar e vermelho
   aparecem só em leituras e veredictos. Os botões não têm cor própria. Num
   aparelho de diagnóstico, se o botão «Limpar» também fosse colorido, a cor
   deixaria de querer dizer alguma coisa.
2. **A elevação transmite hierarquia.** Quatro níveis de superfície, do fundo
   da janela ao elemento em foco. Nunca se empilham dois níveis iguais.
3. **O espaçamento segue uma escala.** Nada de 13px porque «ficava bem»: cada
   medida sai de ESCALA, o que dá ritmo ao conjunto sem ninguém reparar porquê.
"""
from pathlib import Path

# --- Escala de espaçamento ---------------------------------------------------
XS, SM, MD, LG, XL, XXL = 4, 8, 14, 20, 28, 40

# --- Superfícies: quatro níveis de elevação ---------------------------------
FUNDO = "#0d0f12"            # 0 — o poço da janela
CHROME = "#131619"           # 1 — barra lateral e cabeçalho
SUPERFICIE = "#191d21"       # 2 — painéis
ELEVADA = "#20252a"          # 3 — listas, campos e elementos em foco
REALCE = "#272d33"           # hover

ARESTA = "rgba(255, 255, 255, 0.07)"
ARESTA_FORTE = "rgba(255, 255, 255, 0.12)"
ARESTA_LUZ = "rgba(255, 255, 255, 0.05)"   # luz a bater no rebordo superior

# Valores sólidos para o desenho com QPainter, que não interpreta rgba()
TRILHO = "#242a30"
GRADUACAO = "#39414a"
SOMBRA_COR = (0, 0, 0, 90)

# --- Tinta -------------------------------------------------------------------
TINTA = "#e9ecef"
TINTA_SUAVE = "#98a1ab"
TINTA_FRACA = "#6a737d"

# --- Estado de medição: o único sítio onde há cor ---------------------------
# Tons calibrados para fundo escuro — os do tema claro ficavam ilegíveis aqui.
NOMINAL = "#3ecf8e"
CAUTELA = "#e8a33d"
FALHA = "#f26d63"
LEITURA = "#5ac8d8"          # foco e seleção

NOMINAL_FUNDO = "rgba(62, 207, 142, 0.14)"
CAUTELA_FUNDO = "rgba(232, 163, 61, 0.14)"
FALHA_FUNDO = "rgba(242, 109, 99, 0.14)"

NIVEL_CORES = {"critico": FALHA, "alto": FALHA, "medio": CAUTELA, "ok": NOMINAL}

LIMIAR_ATENCAO = 75
LIMIAR_CRITICO = 90

# --- Tipografia --------------------------------------------------------------
# Incluídas no repositório (OFL): a aplicação vê-se igual no Mac, no Windows e
# no servidor. Sem isto, o Qt caía em Helvetica Neue e parecia software de 1998.
PASTA_FONTES = Path(__file__).parent / "fontes"
FAMILIA_UI = "Inter"
FAMILIA_MONO = "JetBrains Mono"
FONTE_UI = f'"{FAMILIA_UI}", "SF Pro Text", "Segoe UI Variable Text", "Segoe UI", sans-serif'
FONTE_MONO = f'"{FAMILIA_MONO}", "SF Mono", Menlo, Consolas, monospace'

DURACAO_PAGINA = 240


def cor_medicao(valor: float, invertido: bool = False) -> str:
    """Cor de uma leitura. `invertido=True` quando mais é melhor."""
    if invertido:
        if valor >= LIMIAR_ATENCAO:
            return NOMINAL
        if valor >= 50:
            return CAUTELA
        return FALHA
    if valor >= LIMIAR_CRITICO:
        return FALHA
    if valor >= LIMIAR_ATENCAO:
        return CAUTELA
    return NOMINAL


QSS = f"""
QWidget {{
    background: transparent;
    color: {TINTA};
    font-family: {FONTE_UI};
    font-size: 13px;
}}
QLabel {{ background: transparent; }}
QMainWindow, QDialog {{ background: {FUNDO}; }}
#fundoJanela {{ background: {FUNDO}; }}

/* --- Barra lateral -------------------------------------------------------- */
#lateral {{ background: {CHROME}; border-right: 1px solid {ARESTA}; }}
#marca {{ color: {TINTA}; font-size: 15px; font-weight: 600; letter-spacing: -.01em; }}
#modelo {{
    color: {TINTA_FRACA}; font-family: {FONTE_MONO}; font-size: 9px;
    font-weight: 500; letter-spacing: .2em;
}}
QPushButton#nav {{
    background: transparent; color: {TINTA_SUAVE}; border: none; text-align: left;
    padding: {SM}px 11px; font-size: 13px; font-weight: 500;
    margin: 1px {MD}px; border-radius: 7px;
}}
QPushButton#nav:hover {{ background: rgba(255, 255, 255, 0.05); color: {TINTA}; }}
QPushButton#nav:checked {{
    background: {ELEVADA}; color: {TINTA}; font-weight: 600;
}}
#separadorLateral {{ background: {ARESTA}; border: none; max-height: 1px; }}

/* Cartão da máquina em intervenção */
QFrame#cartaoMaquina {{
    background: {SUPERFICIE}; border: 1px solid {ARESTA}; border-radius: 9px;
}}
#maquinaRotulo {{
    color: {TINTA_FRACA}; font-family: {FONTE_MONO}; font-size: 8.5px;
    font-weight: 600; letter-spacing: .18em;
}}
#maquinaNome {{ color: {TINTA}; font-size: 12.5px; font-weight: 600; }}
#maquinaDetalhe {{ color: {TINTA_FRACA}; font-family: {FONTE_MONO}; font-size: 10px; }}

/* --- Tipografia ---------------------------------------------------------- */
#titulo {{ font-size: 23px; font-weight: 600; letter-spacing: -.024em; }}
#legenda {{ color: {TINTA_SUAVE}; font-size: 13px; }}
#rotuloSeccao {{
    color: {TINTA_FRACA}; font-family: {FONTE_MONO}; font-size: 9px;
    letter-spacing: .16em; font-weight: 600;
}}
#leitura {{ font-family: {FONTE_MONO}; font-size: 11px; color: {TINTA_FRACA}; }}

/* --- Painéis ------------------------------------------------------------- */
QFrame#painel {{
    background: {SUPERFICIE};
    border: 1px solid {ARESTA};
    border-top: 1px solid {ARESTA_FORTE};
    border-radius: 12px;
}}

/* --- Ações --------------------------------------------------------------- */
QPushButton {{
    background: {ELEVADA}; color: {TINTA};
    border: 1px solid {ARESTA_FORTE};
    border-radius: 8px; padding: {SM}px 16px; font-weight: 600; font-size: 12.5px;
}}
QPushButton:hover {{ background: {REALCE}; border-color: rgba(255,255,255,0.18); }}
QPushButton:pressed {{ background: {SUPERFICIE}; }}
QPushButton:disabled {{ background: rgba(255,255,255,0.03); color: {TINTA_FRACA};
                        border-color: {ARESTA_LUZ}; }}
QPushButton#secundario {{ background: {ELEVADA}; }}

/* A ação principal de cada página distingue-se pelo contraste, não pela cor */
/* A borda tem de ter cor sólida: com `transparent`, o macOS descarta a folha
   de estilo e volta a desenhar o botão à maneira nativa, sem o fundo. */
QPushButton#primario {{
    background: {TINTA}; color: {FUNDO}; border: 1px solid {TINTA}; font-weight: 600;
}}
QPushButton#primario:hover {{ background: #ffffff; border-color: #ffffff; }}
QPushButton#primario:pressed {{ background: #c9ced4; border-color: #c9ced4; }}
QPushButton#primario:disabled {{ background: rgba(255,255,255,0.09); color: {TINTA_FRACA}; }}
/* Única exceção à regra da cor: apagar é irreversível e tem de o parecer. */
QPushButton#perigo {{
    background: {FALHA_FUNDO}; color: {FALHA}; border: 1px solid rgba(242, 109, 99, 0.35);
}}
QPushButton#perigo:hover {{ background: rgba(242, 109, 99, 0.22); }}

/* --- Listas -------------------------------------------------------------- */
QTreeWidget, QTableWidget, QListWidget, QTextEdit, QPlainTextEdit {{
    background: {ELEVADA}; border: 1px solid {ARESTA}; border-radius: 9px;
    alternate-background-color: transparent;
    font-size: 12.5px; outline: none;
    selection-background-color: rgba(90, 200, 216, 0.16);
}}
QTreeWidget::item, QTableWidget::item, QListWidget::item {{
    padding: 9px 6px; border-bottom: 1px solid rgba(255,255,255,0.04);
}}
QTreeWidget::item:hover {{ background: rgba(255,255,255,0.04); }}
QTreeWidget::item:selected, QListWidget::item:selected {{
    background: rgba(90, 200, 216, 0.14); color: {TINTA};
}}
QHeaderView::section {{
    background: transparent; color: {TINTA_FRACA}; border: none;
    border-bottom: 1px solid {ARESTA_FORTE}; padding: 10px 6px;
    font-family: {FONTE_MONO}; font-size: 9px; letter-spacing: .14em; font-weight: 600;
}}
QTreeWidget::branch {{ background: transparent; }}

/* --- Campos -------------------------------------------------------------- */
QLineEdit, QTextEdit {{
    background: {FUNDO}; border: 1px solid {ARESTA}; border-radius: 8px;
    padding: 9px 11px; color: {TINTA}; selection-background-color: rgba(90,200,216,0.3);
}}
QLineEdit:focus, QTextEdit:focus {{ border: 1px solid {LEITURA}; }}
QLineEdit::placeholder {{ color: {TINTA_FRACA}; }}

QProgressBar {{
    background: rgba(255,255,255,0.07); border: none; border-radius: 2px;
    height: 3px; text-align: center;
}}
QProgressBar::chunk {{ background: {LEITURA}; border-radius: 2px; }}

QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 11px; margin: 3px; }}
QScrollBar::handle:vertical {{ background: rgba(255,255,255,0.14); border-radius: 5px;
                               min-height: 34px; }}
QScrollBar::handle:vertical:hover {{ background: rgba(255,255,255,0.24); }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QCheckBox {{ spacing: {SM}px; color: {TINTA}; }}
QCheckBox::indicator {{
    width: 16px; height: 16px; border: 1.5px solid rgba(255,255,255,0.22);
    border-radius: 4px; background: {FUNDO};
}}
QCheckBox::indicator:hover {{ border-color: rgba(255,255,255,0.4); }}
QCheckBox::indicator:checked {{
    background: {LEITURA}; border-color: {LEITURA}; image: url("{{MARCA}}");
}}
QCheckBox::indicator:disabled {{ background: rgba(255,255,255,0.03);
                                 border-color: rgba(255,255,255,0.08); }}

#avisoAdmin {{
    background: {CAUTELA_FUNDO}; border: 1px solid rgba(232, 163, 61, 0.28);
    border-radius: 9px; padding: 11px 14px; color: {CAUTELA}; font-size: 12.5px;
}}

QMessageBox {{ background: {SUPERFICIE}; }}
QMessageBox QLabel {{ color: {TINTA}; }}
QToolTip {{
    background: {ELEVADA}; color: {TINTA}; border: 1px solid {ARESTA_FORTE};
    border-radius: 6px; padding: 6px 9px;
}}
"""


def _caminho_marca() -> str:
    """Desenha o visto das caixas de seleção e devolve o caminho do ficheiro.

    O QSS não desenha símbolo nenhum quando se define o fundo do indicador: a
    caixa marcada ficava um bloco sólido. A marca tem de vir de uma imagem, e
    esta é gerada em código para acompanhar a paleta.
    """
    from PySide6.QtCore import QPointF, Qt  # noqa: PLC0415 - só é preciso na interface
    from PySide6.QtGui import QColor, QPainter, QPen, QPixmap

    from .. import storage

    destino = storage.data_dir() / "marca-verificacao.png"
    lado = 32
    imagem = QPixmap(lado, lado)
    imagem.fill(Qt.transparent)

    pintor = QPainter(imagem)
    pintor.setRenderHint(QPainter.Antialiasing)
    caneta = QPen(QColor(FUNDO))
    caneta.setWidthF(4.0)
    caneta.setCapStyle(Qt.RoundCap)
    caneta.setJoinStyle(Qt.RoundJoin)
    pintor.setPen(caneta)
    pintor.drawPolyline([QPointF(8, 16.5), QPointF(13.5, 22), QPointF(24, 10)])
    pintor.end()

    imagem.save(str(destino))
    return destino.as_posix()


def aplicar(aplicacao) -> None:
    """Prepara a aparência da aplicação: fontes, fonte base e folha de estilo.

    Ponto único para que a janela, as capturas e os testes vejam exatamente o
    mesmo — nada pior do que um screenshot que não corresponde ao produto.
    """
    from PySide6.QtGui import QFont, QFontDatabase  # noqa: PLC0415

    if PASTA_FONTES.is_dir():
        for ficheiro in sorted(PASTA_FONTES.glob("*.ttf")):
            QFontDatabase.addApplicationFont(str(ficheiro))

    base = QFont(FAMILIA_UI, 13)
    base.setStyleStrategy(QFont.PreferAntialias)
    aplicacao.setFont(base)
    aplicacao.setStyleSheet(QSS.replace("{MARCA}", _caminho_marca()))
