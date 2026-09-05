"""Geração do relatório para entregar ao cliente (HTML, PDF e JSON)."""
from __future__ import annotations

import html
import json
from datetime import datetime
from pathlib import Path

from .. import storage
from ..platform_info import APP_VERSION, BRAND, os_label

# A mesma paleta da aplicação: o cliente reconhece o documento como saído
# da ferramenta que viu no ecrã.
NOMINAL, CAUTELA, FALHA = "#1d7a4d", "#b06800", "#a5281f"
TINTA, TINTA_SUAVE, RÉGUA = "#12161b", "#5f6873", "#e2e6ea"
LIMIAR_ATENCAO = 75

NIVEIS = {
    "critico": ("Falha", FALHA),
    "alto": ("Prioritário", FALHA),
    "medio": ("Cautela", CAUTELA),
    "ok": ("Nominal", NOMINAL),
}

MONO = ('"JetBrains Mono", "SF Mono", Menlo, "Cascadia Mono", Consolas, '
        '"DejaVu Sans Mono", monospace')
SANS = ('Inter, "SF Pro Text", "Segoe UI Variable Text", "Segoe UI", '
        '"Helvetica Neue", Arial, sans-serif')


def _cor_saude(valor: int) -> str:
    if valor >= LIMIAR_ATENCAO:
        return NOMINAL
    return CAUTELA if valor >= 50 else FALHA


def _slug(texto: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in texto.lower()).strip("-") or "cliente"


def _linha(rotulo: str, valor) -> str:
    return f"<tr><th>{html.escape(str(rotulo))}</th><td>{html.escape(str(valor))}</td></tr>"


def build_html(snapshot: dict, contexto: dict | None = None) -> str:
    contexto = contexto or {}
    cliente = contexto.get("cliente", "—")
    tecnico = contexto.get("tecnico", "—")
    notas = contexto.get("notas", "")
    acoes = contexto.get("acoes", [])

    sistema = snapshot.get("sistema", {})
    cpu = snapshot.get("cpu", {})
    memoria = snapshot.get("memoria", {})
    pontuacao = snapshot.get("pontuacao", 0)
    cor_pontuacao = _cor_saude(pontuacao)
    veredicto = ("dentro dos valores normais" if pontuacao >= LIMIAR_ATENCAO
                 else "requer atenção" if pontuacao >= 50 else "intervenção necessária")

    conclusoes = "".join(
        f'''<div class="conclusao" style="border-left-color:{NIVEIS.get(item["nivel"], NIVEIS["medio"])[1]}">
              <span class="etiqueta" style="color:{NIVEIS.get(item["nivel"], NIVEIS["medio"])[1]}">
                {NIVEIS.get(item["nivel"], NIVEIS["medio"])[0]}</span>
              <h4>{html.escape(item["titulo"])}</h4>
              <p>{html.escape(item["detalhe"])}</p>
              <p class="acao">{html.escape(item["acao"])}</p>
            </div>'''
        for item in snapshot.get("conclusoes", [])
    )

    particoes = "".join(
        f"<tr><td>{html.escape(p.get('nome', p['ponto_montagem']))}</td><td>{p['total_legivel']}</td>"
        f"<td>{p['usado_legivel']}</td><td>{p['livre_legivel']}</td>"
        f"<td>{p['utilizacao_pct']:.0f}%</td></tr>"
        for p in snapshot.get("particoes", [])
    )

    discos = "".join(
        f"<tr><td>{html.escape(d['nome'])}</td><td>{html.escape(d['tipo'])}</td>"
        f"<td>{html.escape(d['capacidade'])}</td><td>{html.escape(d['saude'])}</td></tr>"
        for d in snapshot.get("discos_fisicos", [])
    ) or '<tr><td colspan="4">Sem informação disponível</td></tr>'

    processos = "".join(
        f"<tr><td>{html.escape(p['nome'])}</td><td>{p['cpu_pct']}%</td><td>{p['memoria_legivel']}</td></tr>"
        for p in snapshot.get("processos", [])[:10]
    )

    bateria = snapshot.get("bateria")
    bloco_bateria = ""
    if bateria:
        bloco_bateria = f"""
        <h3>Bateria</h3>
        <table class="dados">
          {_linha("Carga atual", f"{bateria['percentagem']}%")}
          {_linha("Ligado à corrente", "Sim" if bateria["ligado_corrente"] else "Não")}
          {_linha("Estado", bateria["saude"])}
          {_linha("Ciclos de carga", bateria["ciclos"])}
        </table>"""

    bloco_acoes = ""
    if acoes:
        itens = "".join(f"<li>{html.escape(str(a))}</li>" for a in acoes)
        bloco_acoes = f"<h3>Intervenções realizadas</h3><ul class='acoes'>{itens}</ul>"

    bloco_notas = f"<h3>Observações do técnico</h3><p>{html.escape(notas)}</p>" if notas else ""

    return f"""<!doctype html>
<html lang="pt">
<head>
<meta charset="utf-8">
<title>Relatório de diagnóstico — {html.escape(cliente)}</title>
<style>
  :root {{ color-scheme: light; }}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: {SANS}; margin: 0; padding: 40px 32px; color: {TINTA};
    background: #fff; line-height: 1.55; font-size: 13.5px;
    -webkit-font-smoothing: antialiased;
  }}
  .folha {{ max-width: 820px; margin: 0 auto; }}
  .mono {{ font-family: {MONO}; font-variant-numeric: tabular-nums; }}

  header {{
    display: flex; justify-content: space-between; align-items: flex-start;
    padding-bottom: 18px; margin-bottom: 26px; border-bottom: 2px solid {TINTA};
  }}
  .marca {{ font-size: 19px; font-weight: 700; letter-spacing: -.02em; }}
  .marca span {{
    display: block; font-family: {MONO}; font-size: 9px; font-weight: 600;
    letter-spacing: .18em; color: {TINTA_SUAVE}; margin-top: 2px;
  }}
  h1 {{ font-size: 15px; font-weight: 600; margin: 14px 0 0; letter-spacing: -.01em; }}
  .meta {{ font-family: {MONO}; font-size: 11px; color: {TINTA_SUAVE}; text-align: right;
           line-height: 1.9; }}
  .meta b {{ color: {TINTA}; font-weight: 600; }}

  h2 {{
    font-family: {MONO}; font-size: 10px; font-weight: 600; letter-spacing: .14em;
    color: {TINTA_SUAVE}; margin: 34px 0 12px; text-transform: uppercase;
  }}
  h3 {{
    font-family: {MONO}; font-size: 9.5px; font-weight: 600; letter-spacing: .14em;
    color: {TINTA_SUAVE}; margin: 24px 0 8px; text-transform: uppercase;
  }}

  /* Índice de saúde: a mesma escala calibrada que aparece na aplicação,
     com as três zonas à vista para o número não parecer arbitrário. */
  .indice {{ display: flex; align-items: baseline; gap: 12px; margin-bottom: 12px; }}
  .indice .valor {{
    font-family: {MONO}; font-size: 40px; font-weight: 700; line-height: 1;
    color: {cor_pontuacao}; letter-spacing: -.03em;
  }}
  .indice .escala-rotulo {{ font-family: {MONO}; font-size: 11px; color: {TINTA_SUAVE}; }}
  .indice .veredicto {{ font-size: 13px; color: {TINTA_SUAVE}; }}
  .escala {{ position: relative; height: 9px; display: flex; margin-bottom: 4px; }}
  .escala i {{ display: block; height: 100%; }}
  .escala .agulha {{
    position: absolute; top: -4px; bottom: -4px; width: 2px;
    background: {cor_pontuacao}; left: calc({pontuacao}% - 1px);
  }}
  .graduacao {{
    display: flex; justify-content: space-between; font-family: {MONO};
    font-size: 9px; color: {TINTA_SUAVE}; margin-bottom: 22px;
  }}

  table {{ width: 100%; border-collapse: collapse; font-size: 12.5px; }}
  th, td {{ text-align: left; padding: 7px 10px 7px 0; border-bottom: 1px solid {RÉGUA};
            vertical-align: top; }}
  table.dados th {{ width: 200px; color: {TINTA_SUAVE}; font-weight: 400; }}
  table.dados td {{ font-family: {MONO}; font-size: 12px; }}
  table.lista thead th {{
    font-family: {MONO}; font-size: 9px; letter-spacing: .12em; color: {TINTA_SUAVE};
    font-weight: 600; text-transform: uppercase; border-bottom: 1.5px solid {TINTA};
    padding-bottom: 6px;
  }}
  table.lista td {{ font-family: {MONO}; font-size: 12px; }}
  table.lista td:first-child {{ font-family: {SANS}; font-size: 12.5px; }}

  .conclusao {{ border-left: 3px solid {RÉGUA}; padding: 2px 0 2px 14px; margin-bottom: 18px; }}
  .conclusao h4 {{ margin: 5px 0 3px; font-size: 13.5px; font-weight: 600; }}
  .conclusao p {{ margin: 0 0 3px; font-size: 12.5px; color: {TINTA_SUAVE}; }}
  .conclusao .acao {{ color: {TINTA}; }}
  .etiqueta {{
    font-family: {MONO}; font-size: 9.5px; font-weight: 700; letter-spacing: .12em;
    text-transform: uppercase;
  }}
  ul.acoes {{ font-size: 12.5px; padding-left: 18px; margin: 0; }}
  ul.acoes li {{ margin-bottom: 4px; }}

  footer {{
    margin-top: 44px; padding-top: 14px; border-top: 1px solid {RÉGUA};
    font-family: {MONO}; font-size: 9.5px; color: {TINTA_SUAVE}; line-height: 1.8;
  }}
  @media print {{
    body {{ padding: 0; }}
    .conclusao, table {{ break-inside: avoid; }}
  }}
</style>
</head>
<body>
<div class="folha">
  <header>
    <div>
      <div class="marca">{html.escape(BRAND)}<span>OPTIMIZER</span></div>
      <h1>Relatório de diagnóstico e manutenção</h1>
    </div>
    <div class="meta">
      <div>CLIENTE &nbsp; <b>{html.escape(cliente)}</b></div>
      <div>TÉCNICO &nbsp; <b>{html.escape(tecnico)}</b></div>
      <div>{snapshot.get("gerado_em", datetime.now().strftime("%d/%m/%Y %H:%M"))}</div>
    </div>
  </header>

  <h2>Índice de saúde do sistema</h2>
  <div class="indice">
    <span class="valor">{pontuacao}</span>
    <span class="escala-rotulo">/100</span>
    <span class="veredicto">{veredicto}</span>
  </div>
  <div class="escala">
    <i style="width:50%;background:{FALHA}30"></i>
    <i style="width:25%;background:{CAUTELA}30"></i>
    <i style="width:25%;background:{NOMINAL}30"></i>
    <span class="agulha"></span>
  </div>
  <div class="graduacao"><span>0</span><span>50</span><span>75</span><span>100</span></div>
  <p style="font-size:12px;color:{TINTA_SUAVE};margin:-14px 0 0">
    Calculado a partir do espaço livre em disco, uso de memória e processador,
    estado SMART dos discos e número de programas de arranque. Abaixo de 75
    considera-se que há trabalho a fazer.
  </p>

  <h2>Conclusões</h2>
  {conclusoes}

  {bloco_acoes}
  {bloco_notas}

  <h2>Ficha técnica do equipamento</h2>
  <table class="dados">
    {_linha("Sistema operativo", sistema.get("sistema", "n/d"))}
    {_linha("Equipamento", sistema.get("modelo", "n/d"))}
    {_linha("Número de série", sistema.get("numero_serie", "n/d"))}
    {_linha("Nome na rede", sistema.get("hostname", "n/d"))}
    {_linha("Processador", cpu.get("modelo", "n/d"))}
    {_linha("Núcleos", f"{cpu.get('nucleos_fisicos', '?')} físicos / {cpu.get('nucleos_logicos', '?')} lógicos")}
    {_linha("Utilização do processador", f"{cpu.get('utilizacao_pct', 0):.0f}%")}
    {_linha("Memória RAM", f"{memoria.get('total_legivel', 'n/d')} "
            f"({memoria.get('utilizacao_pct', 0):.0f}% em uso)")}
    {_linha("Placa gráfica", ", ".join(snapshot.get("gpu", [])) or "n/d")}
    {_linha("Ligado desde", f"{sistema.get('arranque', 'n/d')} ({sistema.get('tempo_ligado', 'n/d')})")}
  </table>

  <h3>Armazenamento</h3>
  <table class="lista">
    <thead><tr><th>Unidade</th><th>Capacidade</th><th>Ocupado</th><th>Livre</th><th>%</th></tr></thead>
    <tbody>{particoes}</tbody>
  </table>

  <h3>Estado dos discos</h3>
  <table class="lista">
    <thead><tr><th>Disco</th><th>Tipo</th><th>Capacidade</th><th>Saúde (SMART)</th></tr></thead>
    <tbody>{discos}</tbody>
  </table>
  {bloco_bateria}

  <h3>Programas com maior consumo</h3>
  <table class="lista">
    <thead><tr><th>Programa</th><th>Processador</th><th>Memória</th></tr></thead>
    <tbody>{processos}</tbody>
  </table>

  <footer>
    Relatório gerado por {html.escape(BRAND)} Optimizer {APP_VERSION} em {os_label()}.
    Os valores refletem o estado da máquina no momento da análise.
  </footer>
</div>
</body>
</html>"""


def save_html(snapshot: dict, contexto: dict | None = None, destino: Path | None = None) -> Path:
    contexto = contexto or {}
    nome = f"relatorio-{_slug(contexto.get('cliente', 'cliente'))}-{datetime.now():%Y%m%d-%H%M}.html"
    caminho = destino or (storage.reports_dir() / nome)
    caminho.write_text(build_html(snapshot, contexto), encoding="utf-8")
    storage.log(f"RELATÓRIO HTML gerado: {caminho}")
    return caminho


def save_json(snapshot: dict, contexto: dict | None = None, destino: Path | None = None) -> Path:
    contexto = contexto or {}
    nome = f"diagnostico-{_slug(contexto.get('cliente', 'cliente'))}-{datetime.now():%Y%m%d-%H%M}.json"
    caminho = destino or (storage.reports_dir() / nome)
    payload = {"contexto": contexto, "diagnostico": snapshot}
    caminho.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return caminho


def save_pdf(snapshot: dict, contexto: dict | None = None, destino: Path | None = None) -> Path:
    """Gera o PDF de entrega. Requer reportlab (`pip install reportlab`)."""
    from reportlab.lib import colors  # noqa: PLC0415 - dependência opcional
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        HRFlowable,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    contexto = contexto or {}
    nome = f"relatorio-{_slug(contexto.get('cliente', 'cliente'))}-{datetime.now():%Y%m%d-%H%M}.pdf"
    caminho = destino or (storage.reports_dir() / nome)

    estilos = getSampleStyleSheet()
    titulo = ParagraphStyle("titulo", parent=estilos["Heading1"], fontSize=17, spaceAfter=2)
    marca = ParagraphStyle("marca", parent=estilos["Normal"], fontSize=18,
                           textColor=colors.HexColor("#12161b"), spaceAfter=2)
    seccao = ParagraphStyle("seccao", parent=estilos["Heading2"], fontSize=12,
                            textColor=colors.HexColor("#5f6873"), spaceBefore=14, spaceAfter=6)
    corpo = ParagraphStyle("corpo", parent=estilos["Normal"], fontSize=9, leading=13)
    pequeno = ParagraphStyle("pequeno", parent=estilos["Normal"], fontSize=8,
                             textColor=colors.HexColor("#777777"))

    doc = SimpleDocTemplate(
        str(caminho), pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
        title=f"Relatório de diagnóstico — {contexto.get('cliente', '')}", author=BRAND,
    )

    def tabela(linhas, larguras, cabecalho=False):
        tabela_ = Table(linhas, colWidths=larguras, hAlign="LEFT")
        estilo = [
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#e0e0e0")),
        ]
        if cabecalho:
            estilo += [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f2f4f6")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]
        else:
            estilo += [("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                       ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#555555"))]
        tabela_.setStyle(TableStyle(estilo))
        return tabela_

    sistema = snapshot.get("sistema", {})
    cpu = snapshot.get("cpu", {})
    memoria = snapshot.get("memoria", {})
    largura = doc.width

    fluxo = [
        Paragraph(BRAND, marca),
        Paragraph("Relatório de diagnóstico e manutenção", titulo),
        Paragraph(
            f"Cliente: <b>{html.escape(str(contexto.get('cliente', '—')))}</b> &nbsp;|&nbsp; "
            f"Técnico: {html.escape(str(contexto.get('tecnico', '—')))} &nbsp;|&nbsp; "
            f"{snapshot.get('gerado_em', '')}",
            pequeno,
        ),
        Spacer(1, 6),
        HRFlowable(width="100%", thickness=2, color=colors.HexColor("#12161b")),
        Spacer(1, 10),
        Paragraph(
            f"<font size=22 color='{_cor_saude(snapshot.get('pontuacao', 0))}'>"
            f"<b>{snapshot.get('pontuacao', 0)}</b></font>"
            "<font size=9> / 100 &nbsp; índice de saúde do sistema</font>",
            corpo,
        ),
        Paragraph("Conclusões", seccao),
    ]

    for item in snapshot.get("conclusoes", []):
        rotulo, cor = NIVEIS.get(item["nivel"], NIVEIS["medio"])
        fluxo.append(Paragraph(
            f"<font color='{cor}'><b>[{rotulo}]</b></font> <b>{html.escape(item['titulo'])}</b>", corpo))
        fluxo.append(Paragraph(html.escape(item["detalhe"]), corpo))
        fluxo.append(Paragraph(f"<i>Recomendação: {html.escape(item['acao'])}</i>", corpo))
        fluxo.append(Spacer(1, 8))

    if contexto.get("acoes"):
        fluxo.append(Paragraph("Intervenções realizadas", seccao))
        for acao in contexto["acoes"]:
            fluxo.append(Paragraph(f"• {html.escape(str(acao))}", corpo))

    if contexto.get("notas"):
        fluxo.append(Paragraph("Observações do técnico", seccao))
        fluxo.append(Paragraph(html.escape(str(contexto["notas"])), corpo))

    fluxo.append(Paragraph("Ficha técnica", seccao))
    fluxo.append(tabela(
        [
            ["Sistema operativo", str(sistema.get("sistema", "n/d"))],
            ["Equipamento", str(sistema.get("modelo", "n/d"))],
            ["Número de série", str(sistema.get("numero_serie", "n/d"))],
            ["Processador", str(cpu.get("modelo", "n/d"))],
            ["Núcleos", f"{cpu.get('nucleos_fisicos', '?')} físicos / {cpu.get('nucleos_logicos', '?')} lógicos"],
            ["Memória RAM", f"{memoria.get('total_legivel', 'n/d')} ({memoria.get('utilizacao_pct', 0):.0f}% em uso)"],
            ["Placa gráfica", ", ".join(snapshot.get("gpu", [])) or "n/d"],
            ["Ligado há", str(sistema.get("tempo_ligado", "n/d"))],
        ],
        [largura * 0.28, largura * 0.72],
    ))

    fluxo.append(Paragraph("Armazenamento", seccao))
    fluxo.append(tabela(
        [["Unidade", "Capacidade", "Ocupado", "Livre", "%"]]
        + [
            [p.get("nome", p["ponto_montagem"]), p["total_legivel"], p["usado_legivel"], p["livre_legivel"],
             f"{p['utilizacao_pct']:.0f}%"]
            for p in snapshot.get("particoes", [])
        ],
        [largura * 0.32, largura * 0.17, largura * 0.17, largura * 0.17, largura * 0.17],
        cabecalho=True,
    ))

    discos = snapshot.get("discos_fisicos", [])
    if discos:
        fluxo.append(Paragraph("Estado dos discos", seccao))
        fluxo.append(tabela(
            [["Disco", "Tipo", "Capacidade", "Saúde (SMART)"]]
            + [[d["nome"], d["tipo"], d["capacidade"], d["saude"]] for d in discos],
            [largura * 0.40, largura * 0.16, largura * 0.20, largura * 0.24],
            cabecalho=True,
        ))

    processos = snapshot.get("processos", [])
    if processos:
        fluxo.append(Paragraph("Programas com maior consumo", seccao))
        fluxo.append(tabela(
            [["Programa", "Processador", "Memória"]]
            + [[p["nome"], f"{p['cpu_pct']}%", p["memoria_legivel"]] for p in processos[:10]],
            [largura * 0.50, largura * 0.25, largura * 0.25],
            cabecalho=True,
        ))

    fluxo.append(Spacer(1, 16))
    fluxo.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#dddddd")))
    fluxo.append(Paragraph(
        f"Gerado por {BRAND} Optimizer {APP_VERSION} em {os_label()}. "
        "Os valores refletem o estado da máquina no momento da análise.", pequeno))

    doc.build(fluxo)
    storage.log(f"RELATÓRIO PDF gerado: {caminho}")
    return caminho
