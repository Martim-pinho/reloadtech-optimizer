"""Identidade visual: instrumento de bancada em materiais translúcidos.

Duas ideias governam tudo:

1. A cor significa o estado de uma medição. Verde, âmbar e vermelho aparecem
   só em leituras e veredictos — nunca em botões ou decoração. Num aparelho de
   diagnóstico, se o botão «Limpar» também fosse colorido, a cor deixaria de
   querer dizer alguma coisa.
2. O material transmite hierarquia. A barra lateral é o material pesado que
   separa regiões estruturais; os painéis são o material leve onde o trabalho
   acontece. Nunca se empilha material leve sobre material leve.

Nota técnica sobre o vidro: o Qt não acede ao desfoque do ambiente de trabalho
sem código nativo. Como o fundo da janela é um gradiente de baixa frequência
desenhado por nós, uma camada branca translúcida por cima é opticamente
equivalente a desfocá-lo — e custa uma fração do desempenho.
"""

# --- Fundo da janela: gradiente suave, não um cinzento chapado --------------
FUNDO_TOPO = "#eff2f7"
FUNDO_BASE = "#dde3ea"
BRILHO = "#ffffff"          # foco de luz difusa no canto superior esquerdo

# --- Materiais ---------------------------------------------------------------
VIDRO = "rgba(255, 255, 255, 0.72)"        # painel leve
VIDRO_FORTE = "rgba(255, 255, 255, 0.86)"  # campos e listas sobre o painel
ARESTA_LUZ = "rgba(255, 255, 255, 0.9)"    # a luz a bater no rebordo superior
ARESTA = "rgba(17, 24, 33, 0.09)"
SOMBRA = (0, 0, 0, 28)

GRAFITE = "#20252b"          # material pesado: barra lateral e ações
GRAFITE_CLARO = "#2c333b"
GRAFITE_TOPO = "#31383f"
PAINEL = "#ffffff"
RÉGUA = "rgba(17, 24, 33, 0.10)"
RÉGUA_SOLIDA = "#dde1e6"
TRILHO = "#dfe4e9"

# --- Tinta -------------------------------------------------------------------
TINTA = "#12161b"
TINTA_SUAVE = "#5f6873"
TINTA_RAIL = "#98a2ad"

# --- Estado de medição: o único sítio onde há cor ---------------------------
NOMINAL = "#1d7a4d"
CAUTELA = "#b06800"
FALHA = "#a5281f"
LEITURA = "#0b6a72"

NIVEL_CORES = {"critico": FALHA, "alto": FALHA, "medio": CAUTELA, "ok": NOMINAL}

LIMIAR_ATENCAO = 75
LIMIAR_CRITICO = 90

FONTE_UI = '"Inter", "SF Pro Text", "Segoe UI Variable Text", "Segoe UI", "Helvetica Neue", "DejaVu Sans", sans-serif'
FONTE_MONO = '"JetBrains Mono", "SF Mono", "Menlo", "Cascadia Mono", "Consolas", "DejaVu Sans Mono", monospace'

# Movimento: curto, sem ressalto por omissão. O ressalto guarda-se para gestos
# que trazem inércia — e esta aplicação não tem nenhum.
DURACAO_PAGINA = 260
DURACAO_ENTRADA = 300


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

/* --- Barra lateral: o material pesado ------------------------------------ */
#lateral {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #262c33, stop:1 #1a1e24);
    border-right: 1px solid rgba(0, 0, 0, 0.35);
}}
#marca {{ color: #ffffff; font-size: 16.5px; font-weight: 700; letter-spacing: -.02em; }}
#modelo {{
    color: {TINTA_RAIL}; font-family: {FONTE_MONO}; font-size: 9.5px;
    letter-spacing: .18em; padding: 0 20px 22px 20px;
}}
QPushButton#nav {{
    background: transparent; color: #b3bcc6; border: none; text-align: left;
    padding: 10px 20px; font-size: 13px; margin: 1px 10px; border-radius: 7px;
}}
QPushButton#nav:hover {{ background: rgba(255, 255, 255, 0.06); color: #ffffff; }}
QPushButton#nav:checked {{
    background: rgba(255, 255, 255, 0.11); color: #ffffff; font-weight: 600;
}}
/* Sem borda: uma regra com `border` faz o Qt desenhar o fundo da paleta por
   baixo, e a etiqueta ficava um retângulo claro sobre a barra escura. A linha
   de separação é um QFrame à parte. */
#etiquetaServico {{
    background: transparent; color: {TINTA_RAIL};
    font-family: {FONTE_MONO}; font-size: 10px;
    padding: 14px 20px 18px 20px; line-height: 155%;
}}
#separadorLateral {{ background: rgba(255, 255, 255, 0.08); border: none; max-height: 1px; }}

/* --- Tipografia: tracking em função do tamanho -------------------------- */
#titulo {{ font-size: 22px; font-weight: 700; letter-spacing: -.022em; }}
#legenda {{ color: {TINTA_SUAVE}; font-size: 12.5px; }}
#rotuloSeccao {{
    color: {TINTA_SUAVE}; font-family: {FONTE_MONO}; font-size: 9.5px;
    letter-spacing: .14em; font-weight: 600;
}}
#leitura {{ font-family: {FONTE_MONO}; font-size: 11.5px; color: {TINTA_SUAVE}; }}

/* --- Painéis de vidro ---------------------------------------------------- */
QFrame#painel {{
    background: {VIDRO};
    border: 1px solid {ARESTA};
    border-top: 1px solid {ARESTA_LUZ};
    border-radius: 14px;
}}

/* --- Ações: grafite. A cor pertence às medições. ------------------------- */
QPushButton {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {GRAFITE_TOPO}, stop:1 {GRAFITE});
    color: #ffffff; border: 1px solid rgba(0, 0, 0, 0.4);
    border-radius: 8px; padding: 8px 17px; font-weight: 600; font-size: 12.5px;
}}
QPushButton:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #3a424b, stop:1 {GRAFITE_CLARO});
}}
/* Resposta no instante do clique, não à espera do fim */
QPushButton:pressed {{ background: {GRAFITE}; padding-top: 9px; padding-bottom: 7px; }}
QPushButton:disabled {{
    background: rgba(120, 130, 142, 0.28); border-color: transparent; color: rgba(255,255,255,0.65);
}}
QPushButton#secundario {{
    background: {VIDRO_FORTE}; color: {TINTA}; border: 1px solid {ARESTA};
}}
QPushButton#secundario:hover {{ background: #ffffff; }}
QPushButton#secundario:pressed {{ background: #eef1f4; }}
QPushButton#secundario:disabled {{ background: rgba(255,255,255,0.5); color: #a9b1ba; }}
/* Única exceção à regra da cor: apagar é irreversível e tem de o parecer. */
QPushButton#perigo {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #b83229, stop:1 {FALHA});
    border-color: rgba(0, 0, 0, 0.3);
}}
QPushButton#perigo:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #c73a30, stop:1 #ad2b21);
}}

/* --- Listas -------------------------------------------------------------- */
QTreeWidget, QTableWidget, QListWidget, QTextEdit, QPlainTextEdit {{
    background: {VIDRO_FORTE}; border: 1px solid {ARESTA}; border-radius: 9px;
    alternate-background-color: rgba(255, 255, 255, 0.45);
    font-size: 12.5px;
}}
QTreeWidget::item, QTableWidget::item {{ padding: 7px 4px; }}
QTreeWidget::item:selected, QListWidget::item:selected {{
    background: rgba(11, 106, 114, 0.12); color: {TINTA};
}}
QHeaderView::section {{
    background: transparent; color: {TINTA_SUAVE}; border: none;
    border-bottom: 1px solid {RÉGUA}; padding: 8px 6px;
    font-family: {FONTE_MONO}; font-size: 9.5px; letter-spacing: .12em; font-weight: 600;
}}

/* --- Campos -------------------------------------------------------------- */
QLineEdit, QTextEdit {{
    background: {VIDRO_FORTE}; border: 1px solid {ARESTA}; border-radius: 8px; padding: 8px 10px;
}}
QLineEdit:focus, QTextEdit:focus {{ border: 1px solid {LEITURA}; background: #ffffff; }}

QProgressBar {{
    background: rgba(17, 24, 33, 0.08); border: none; border-radius: 2px;
    height: 4px; text-align: center;
}}
QProgressBar::chunk {{ background: {GRAFITE}; border-radius: 2px; }}

QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 11px; margin: 3px; }}
QScrollBar::handle:vertical {{ background: rgba(17,24,33,0.22); border-radius: 5px; min-height: 32px; }}
QScrollBar::handle:vertical:hover {{ background: rgba(17,24,33,0.34); }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px; border: 1.5px solid rgba(17,24,33,0.28);
    border-radius: 4px; background: rgba(255,255,255,0.9);
}}
QCheckBox::indicator:checked {{ background: {GRAFITE}; border-color: {GRAFITE}; }}
QCheckBox::indicator:disabled {{ background: rgba(255,255,255,0.5); border-color: rgba(17,24,33,0.14); }}

#avisoAdmin {{
    background: rgba(176, 104, 0, 0.09); border: 1px solid rgba(176, 104, 0, 0.22);
    border-radius: 9px; padding: 11px 14px; color: #7a4900; font-size: 12.5px;
}}

QMessageBox {{ background: #f1f4f7; }}
QToolTip {{
    background: {GRAFITE}; color: #ffffff; border: none;
    border-radius: 6px; padding: 6px 9px;
}}
"""
