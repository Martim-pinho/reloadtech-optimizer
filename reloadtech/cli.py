"""Interface de linha de comandos — pensada para servidores e uso por SSH."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import storage
from .core import cleaner, diagnostics, report, startup, tweaks
from .platform_info import APP_NAME, APP_VERSION, human_bytes, is_admin, os_label

_CORES = sys.stdout.isatty()


def _c(texto: str, codigo: str) -> str:
    return f"\033[{codigo}m{texto}\033[0m" if _CORES else texto


def negrito(t: str) -> str:
    return _c(t, "1")


def verde(t: str) -> str:
    return _c(t, "32")


def amarelo(t: str) -> str:
    return _c(t, "33")


def vermelho(t: str) -> str:
    return _c(t, "31")


def azul(t: str) -> str:
    return _c(t, "36")


def cinza(t: str) -> str:
    return _c(t, "90")


def cabecalho(titulo: str) -> None:
    print()
    print(negrito(azul(f"── {titulo} ".ljust(70, "─"))))


def _progresso(pct: int, texto: str) -> None:
    if _CORES:
        print(f"\r  {pct:3d}%  {texto[:60]:<60}", end="", flush=True)
        if pct >= 100:
            print("\r" + " " * 70 + "\r", end="")
    elif pct >= 100:
        print(f"  {texto}")


def _cor_percentagem(valor: float) -> str:
    texto = f"{valor:.0f}%"
    if valor >= 90:
        return vermelho(texto)
    if valor >= 75:
        return amarelo(texto)
    return verde(texto)


# --- Diagnóstico -------------------------------------------------------------

def _mostrar_diagnostico(snapshot: dict) -> None:
    sistema = snapshot["sistema"]
    cpu = snapshot["cpu"]
    memoria = snapshot["memoria"]
    pontuacao = snapshot["pontuacao"]
    cor = verde if pontuacao >= 75 else amarelo if pontuacao >= 50 else vermelho

    cabecalho("Sistema")
    print(f"  Equipamento ...... {sistema.get('modelo')}")
    print(f"  Sistema .......... {sistema.get('sistema')}")
    print(f"  Nome na rede ..... {sistema.get('hostname')}")
    print(f"  Ligado há ........ {sistema.get('tempo_ligado')}")
    if sistema.get("carga_media"):
        print(f"  Carga média ...... {sistema['carga_media']}")

    cabecalho("Recursos")
    print(f"  Processador ...... {cpu.get('modelo')}")
    print(f"  Uso do CPU ....... {_cor_percentagem(cpu.get('utilizacao_pct', 0))}")
    print(f"  Memória .......... {memoria['usada_legivel']} de {memoria['total_legivel']}  "
          f"({_cor_percentagem(memoria['utilizacao_pct'])})")
    if memoria["swap_pct"]:
        print(f"  Swap ............. {memoria['swap_usada_legivel']} ({memoria['swap_pct']:.0f}%)")

    cabecalho("Armazenamento")
    for particao in snapshot["particoes"]:
        print(f"  {particao.get('nome', particao['ponto_montagem'])[:26]:<26} "
              f"{particao['usado_legivel']:>10} de {particao['total_legivel']:<10} "
              f"{_cor_percentagem(particao['utilizacao_pct']):>14}  "
              f"{cinza('livre: ' + particao['livre_legivel'])}")

    if snapshot["discos_fisicos"]:
        cabecalho("Estado dos discos")
        for disco in snapshot["discos_fisicos"]:
            saudavel = disco["saude"] == "Saudável"
            estado = verde(disco["saude"]) if saudavel else vermelho(disco["saude"])
            print(f"  {disco['nome'][:38]:<38} {disco['tipo']:<10} {disco['capacidade']:<12} {estado}")

    if snapshot["processos"]:
        cabecalho("Processos com maior consumo")
        for proc in snapshot["processos"][:8]:
            print(f"  {proc['nome'][:32]:<32} CPU {proc['cpu_pct']:>5}%   RAM {proc['memoria_legivel']:>10}")

    cabecalho("Conclusões")
    for item in snapshot["conclusoes"]:
        marcas = {"critico": vermelho("[CRÍTICO] "), "alto": vermelho("[PRIORITÁRIO] "),
                  "medio": amarelo("[A VIGIAR] "), "ok": verde("[OK] ")}
        print(f"  {marcas.get(item['nivel'], '')}{negrito(item['titulo'])}")
        print(f"    {item['detalhe']}")
        print(f"    {cinza('→ ' + item['acao'])}")

    print()
    print(f"  Índice de saúde do sistema: {cor(negrito(str(pontuacao)))}/100")
    print()


def cmd_diagnostico(args) -> int:
    if not args.json:
        print(f"\n{negrito(APP_NAME)} {APP_VERSION} — diagnóstico em {os_label()}")
    snapshot = diagnostics.collect(progress=None if args.json else _progresso)
    snapshot["arranque_total"] = len([i for i in startup.list_items() if i.ativo])
    snapshot["conclusoes"] = diagnostics.build_findings(snapshot)
    snapshot["pontuacao"] = diagnostics.health_score(snapshot)

    if args.json:
        print(json.dumps(snapshot, indent=2, ensure_ascii=False, default=str))
        return 0

    _mostrar_diagnostico(snapshot)
    _guardar_relatorios(snapshot, args)
    return 0


def _guardar_relatorios(snapshot: dict, args) -> None:
    contexto = {"cliente": getattr(args, "cliente", "") or "—",
                "tecnico": getattr(args, "tecnico", "") or "—",
                "notas": getattr(args, "notas", "") or "",
                "acoes": getattr(args, "_acoes", [])}
    if getattr(args, "html", None):
        destino = report.save_html(snapshot, contexto, Path(args.html) if args.html != "auto" else None)
        print(f"  {verde('✓')} Relatório HTML: {destino}")
    if getattr(args, "pdf", None):
        try:
            destino = report.save_pdf(snapshot, contexto, Path(args.pdf) if args.pdf != "auto" else None)
            print(f"  {verde('✓')} Relatório PDF: {destino}")
        except ImportError:
            print(f"  {vermelho('✗')} PDF indisponível — instala com: pip install reportlab")


# --- Limpeza -----------------------------------------------------------------

def cmd_limpeza(args) -> int:
    alvos = cleaner.available_targets()
    if args.alvos:
        pedidos = {a.strip() for a in args.alvos.split(",")}
        alvos = [alvo for alvo in alvos if alvo.key in pedidos]
        if not alvos:
            print(vermelho("Nenhum alvo corresponde ao que foi indicado."))
            return 1
    if args.seguros:
        alvos = [alvo for alvo in alvos if alvo.risco == cleaner.SAFE]

    print(f"\n{negrito('Análise de ficheiros descartáveis')} ({os_label()})")
    resultados = cleaner.scan(alvos, progress=_progresso)
    total = sum(r.bytes for r in resultados)

    cabecalho("Encontrado")
    for resultado in sorted(resultados, key=lambda r: r.bytes, reverse=True):
        marca = "  " if resultado.target.risco == cleaner.SAFE else amarelo("! ")
        erro = f"  {cinza(resultado.error)}" if resultado.error else ""
        print(f"{marca}{resultado.target.nome:<42} {resultado.readable:>12}{erro}")
    print()
    print(f"  Total recuperável: {negrito(human_bytes(total))}")
    if any(r.target.risco != cleaner.SAFE for r in resultados):
        print(f"  {amarelo('!')} = alvo que convém rever antes de limpar")

    if not args.executar:
        print(cinza("\n  Análise apenas. Acrescenta --executar para limpar.\n"))
        return 0

    if not args.sim:
        try:
            resposta = input(f"\n  Limpar {human_bytes(total)}? [s/N] ").strip().lower()
        except EOFError:
            resposta = "n"
        if resposta not in ("s", "sim", "y"):
            print("  Cancelado.\n")
            return 0

    print()
    limpos = cleaner.clean([r.target for r in resultados if r.bytes > 0], progress=_progresso)
    libertado = sum(r.bytes for r in limpos)
    print(f"\n  {verde('✓')} Libertado: {negrito(human_bytes(libertado))}\n")
    return 0


# --- Arranque ----------------------------------------------------------------

def cmd_arranque(args) -> int:
    itens = startup.list_items()

    if args.desativar or args.ativar:
        chave = args.desativar or args.ativar
        ativar = bool(args.ativar)
        alvo = next((i for i in itens if i.key == chave or i.nome == chave or i.referencia == chave), None)
        if alvo is None:
            print(vermelho(f"Não encontrei nenhuma entrada de arranque chamada '{chave}'."))
            return 1
        ok, erro = startup.set_enabled(alvo, ativar)
        acao = "ativado" if ativar else "desativado"
        print(f"  {verde('✓') + ' ' + alvo.nome + ' ' + acao if ok else vermelho('✗') + ' ' + erro}")
        return 0 if ok else 1

    ativos = [i for i in itens if i.ativo]
    print(f"\n{negrito('Programas e serviços de arranque')} — "
          f"{len(ativos)} ativos de {len(itens)} encontrados\n")
    for item in itens:
        estado = verde("ativo   ") if item.ativo else cinza("desativado")
        protegido = amarelo(" [essencial]") if startup.is_protected(item) else ""
        print(f"  {estado}  {item.nome[:40]:<40} {cinza(item.origem)}{protegido}")
        if args.detalhado and item.comando:
            print(f"            {cinza(item.comando[:100])}")
            print(f"            {cinza('chave: ' + item.key)}")
    print()
    if not args.detalhado:
        print(cinza("  Usa --detalhado para ver os comandos e as chaves para --desativar.\n"))
    return 0


# --- Otimizações -------------------------------------------------------------

def cmd_otimizacoes(args) -> int:
    disponiveis = tweaks.available_tweaks()

    if args.aplicar or args.reverter:
        chave = args.aplicar or args.reverter
        alvo = next((t for t in disponiveis if t.key == chave), None)
        if alvo is None:
            print(vermelho(f"Otimização '{chave}' não existe neste sistema."))
            return 1
        ok, mensagem = tweaks.apply(alvo) if args.aplicar else tweaks.revert(alvo)
        print(f"  {verde('✓ ' + alvo.nome) if ok else vermelho('✗ ' + (mensagem or 'falhou'))}")
        return 0 if ok else 1

    print(f"\n{negrito('Otimizações disponíveis')} ({os_label()})\n")
    for tweak in disponiveis:
        estado = tweaks.state_of(tweak)
        if tweak.tipo == "acao":
            marca = azul("[ação]    ")
        elif estado is True:
            marca = verde("[aplicada]")
        elif estado is False:
            marca = cinza("[inativa] ")
        else:
            marca = cinza("[?]       ")
        admin = amarelo(" *") if tweak.requires_admin else "  "
        print(f"  {marca}{admin} {negrito(tweak.nome)}  {cinza(tweak.key)}")
        print(f"              {tweak.descricao}")
        print(f"              {cinza('→ ' + tweak.beneficio)}")
    print(f"\n  {amarelo('*')} requer privilégios de administrador"
          f"{'' if is_admin() else cinza(' (não os tens agora)')}")
    print(cinza("  Aplicar: reloadtech otimizacoes --aplicar <chave>\n"))
    return 0


# --- Manutenção automática ---------------------------------------------------

def cmd_manutencao(args) -> int:
    """Rotina completa e não interativa, para cron ou temporizador do systemd."""
    print(f"{APP_NAME} — manutenção automática ({os_label()})")

    resultados = cleaner.scan([t for t in cleaner.available_targets() if t.risco == cleaner.SAFE])
    limpos = cleaner.clean([r.target for r in resultados if r.bytes > 0])
    libertado = sum(r.bytes for r in limpos)
    print(f"Limpeza: {human_bytes(libertado)} libertados")

    snapshot = diagnostics.collect()
    snapshot["arranque_total"] = len([i for i in startup.list_items() if i.ativo])
    snapshot["conclusoes"] = diagnostics.build_findings(snapshot)
    snapshot["pontuacao"] = diagnostics.health_score(snapshot)

    contexto = {"cliente": args.cliente or snapshot["sistema"].get("hostname", "—"),
                "tecnico": args.tecnico or "Manutenção automática",
                "notas": "Relatório gerado automaticamente pela rotina de manutenção.",
                "acoes": [f"Limpeza automática de ficheiros temporários: {human_bytes(libertado)} libertados"]}

    destino = Path(args.destino) if args.destino else None
    caminho = report.save_html(snapshot, contexto, destino)
    print(f"Relatório: {caminho}")
    print(f"Índice de saúde: {snapshot['pontuacao']}/100")

    criticos = [c for c in snapshot["conclusoes"] if c["nivel"] in ("critico", "alto")]
    for item in criticos:
        print(f"ATENÇÃO: {item['titulo']} — {item['detalhe']}")
    storage.log(f"MANUTENÇÃO automática concluída: {human_bytes(libertado)} libertados, "
                f"pontuação {snapshot['pontuacao']}")
    return 2 if criticos else 0


def cmd_registo(args) -> int:
    linhas = storage.read_log(args.linhas)
    if not linhas:
        print("Ainda não há operações registadas.")
        return 0
    print(f"\n{negrito('Registo de operações')}  {cinza(str(storage.log_path()))}\n")
    for linha in linhas:
        print("  " + linha.rstrip())
    print()
    return 0


# --- Ponto de entrada --------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="reloadtech",
        description=f"{APP_NAME} {APP_VERSION} — diagnóstico e otimização de Windows, macOS e Linux.",
        epilog="Sem argumentos abre a interface gráfica (se estiver disponível).",
    )
    parser.add_argument("--versao", action="version", version=f"{APP_NAME} {APP_VERSION}")
    parser.add_argument("--gui", action="store_true", help="abrir a interface gráfica")
    sub = parser.add_subparsers(dest="comando")

    diag = sub.add_parser("diagnostico", help="analisar o estado da máquina")
    diag.add_argument("--json", action="store_true", help="devolver o resultado em JSON")
    diag.add_argument("--html", nargs="?", const="auto", help="gerar relatório HTML (caminho opcional)")
    diag.add_argument("--pdf", nargs="?", const="auto", help="gerar relatório PDF (caminho opcional)")
    diag.add_argument("--cliente", help="nome do cliente para o relatório")
    diag.add_argument("--tecnico", help="nome do técnico para o relatório")
    diag.add_argument("--notas", help="observações a incluir no relatório")
    diag.set_defaults(func=cmd_diagnostico)

    limp = sub.add_parser("limpeza", help="analisar e remover ficheiros descartáveis")
    limp.add_argument("--executar", action="store_true", help="apagar (sem isto só analisa)")
    limp.add_argument("--sim", action="store_true", help="não pedir confirmação")
    limp.add_argument("--seguros", action="store_true", help="apenas alvos de risco baixo")
    limp.add_argument("--alvos", help="lista de chaves separadas por vírgulas")
    limp.set_defaults(func=cmd_limpeza)

    arr = sub.add_parser("arranque", help="listar e gerir o que arranca com o sistema")
    arr.add_argument("--detalhado", action="store_true", help="mostrar comandos e chaves")
    arr.add_argument("--desativar", metavar="CHAVE")
    arr.add_argument("--ativar", metavar="CHAVE")
    arr.set_defaults(func=cmd_arranque)

    opt = sub.add_parser("otimizacoes", help="listar e aplicar otimizações do sistema")
    opt.add_argument("--aplicar", metavar="CHAVE")
    opt.add_argument("--reverter", metavar="CHAVE")
    opt.set_defaults(func=cmd_otimizacoes)

    man = sub.add_parser("manutencao", help="rotina automática (limpeza segura + relatório)")
    man.add_argument("--cliente", help="nome a usar no relatório")
    man.add_argument("--tecnico", help="responsável indicado no relatório")
    man.add_argument("--destino", help="caminho do relatório HTML a escrever")
    man.set_defaults(func=cmd_manutencao)

    reg = sub.add_parser("registo", help="ver o histórico de operações da ferramenta")
    reg.add_argument("--linhas", type=int, default=60)
    reg.set_defaults(func=cmd_registo)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.gui or args.comando is None:
        try:
            from .ui.app import run_gui  # noqa: PLC0415 - dependência opcional
        except ImportError:
            if args.gui:
                print(vermelho("A interface gráfica precisa do PySide6:"))
                print("  pip install 'reloadtech-optimizer[gui]'")
                return 1
            parser.print_help()
            print(cinza("\n  Interface gráfica indisponível (PySide6 não instalado)."))
            print(cinza("  Num servidor é normal — usa os comandos acima.\n"))
            return 0
        return run_gui()

    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\n  Interrompido.\n")
        return 130


if __name__ == "__main__":
    sys.exit(main())
