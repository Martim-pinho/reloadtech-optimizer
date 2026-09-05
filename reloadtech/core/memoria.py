"""Memória: o que a está a ocupar e o que se pode mesmo fazer.

Uma nota que atravessa este módulo: em sistemas modernos, memória livre é
memória desperdiçada. O sistema operativo usa a RAM sobrante como cache de
disco de propósito, e "libertá-la" costuma piorar o desempenho nos minutos
seguintes, porque tudo tem de ser lido outra vez.

Por isso não há aqui nenhum botão mágico. Há três coisas reais:
  * ver o que está mesmo a ocupar a memória,
  * fechar o que não é preciso,
  * e as poucas operações que o sistema suporta de facto, cada uma com o que
    faz e o que custa escrito à frente.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import psutil

from .. import storage
from ..platform_info import (
    IS_LINUX,
    IS_MACOS,
    IS_WINDOWS,
    human_bytes,
    is_admin,
    run,
    run_elevated,
)

# Processos que nunca devem ser terminados: o sistema fica instável ou vai abaixo.
PROTEGIDOS = {
    "kernel_task", "launchd", "WindowServer", "loginwindow", "logind", "systemstats",
    "System", "System Idle Process", "Registry", "smss.exe", "csrss.exe", "wininit.exe",
    "winlogon.exe", "services.exe", "lsass.exe", "svchost.exe", "dwm.exe", "explorer.exe",
    "systemd", "init", "sshd", "dbus-daemon", "systemd-journald", "systemd-logind",
}


@dataclass
class Consumidor:
    pid: int
    nome: str
    memoria: int
    memoria_legivel: str
    percentagem: float
    utilizador: str
    protegido: bool


@dataclass
class AcaoMemoria:
    key: str
    nome: str
    descricao: str
    custo: str            # o que se paga por a fazer — dito à frente
    requires_admin: bool
    disponivel: bool = True


# --- Leitura -----------------------------------------------------------------

def resumo() -> dict:
    """Repartição da memória, com os termos que cada sistema usa."""
    virtual = psutil.virtual_memory()
    swap = psutil.swap_memory()

    dados = {
        "total": virtual.total,
        "usada": virtual.used,
        "disponivel": virtual.available,
        "percentagem": virtual.percent,
        "total_legivel": human_bytes(virtual.total),
        "usada_legivel": human_bytes(virtual.used),
        "disponivel_legivel": human_bytes(virtual.available),
        "swap_total": swap.total,
        "swap_usada": swap.used,
        "swap_legivel": human_bytes(swap.used),
        "swap_percentagem": swap.percent,
        "reparticao": [],
    }

    # A repartição é o que distingue "memória ocupada" de "memória em falta"
    if IS_MACOS:
        dados["reparticao"] = [
            ("Ativa", getattr(virtual, "active", 0), "em uso por programas abertos"),
            ("Retida pelo sistema", getattr(virtual, "wired", 0), "não pode ser movida para disco"),
            ("Inativa", getattr(virtual, "inactive", 0), "libertável de imediato se fizer falta"),
            ("Livre", getattr(virtual, "free", 0), "por atribuir"),
        ]
    elif IS_LINUX:
        dados["reparticao"] = [
            ("Aplicações", virtual.total - virtual.available - getattr(virtual, "buffers", 0)
             - getattr(virtual, "cached", 0), "em uso por processos"),
            ("Cache e buffers", getattr(virtual, "cached", 0) + getattr(virtual, "buffers", 0),
             "cache de disco — libertável de imediato"),
            ("Partilhada", getattr(virtual, "shared", 0), "entre processos"),
            ("Livre", virtual.free, "por atribuir"),
        ]
    else:
        dados["reparticao"] = [
            ("Em uso", virtual.used, "por programas e pelo sistema"),
            ("Disponível", virtual.available, "atribuível sem recorrer ao disco"),
        ]

    dados["reparticao"] = [
        {"nome": nome, "bytes": max(0, valor), "legivel": human_bytes(max(0, valor)),
         "explicacao": explicacao,
         "percentagem": round(max(0, valor) / virtual.total * 100, 1) if virtual.total else 0}
        for nome, valor, explicacao in dados["reparticao"]
    ]
    return dados


def consumidores(limite: int = 25) -> list[Consumidor]:
    """Processos ordenados pela memória que ocupam."""
    total = psutil.virtual_memory().total
    proprio = os.getpid()
    linhas: list[Consumidor] = []

    for processo in psutil.process_iter(["pid", "name", "memory_info", "username"]):
        try:
            info = processo.info
            rss = info["memory_info"].rss if info["memory_info"] else 0
            if rss <= 0:
                continue
            nome = info["name"] or "?"
            linhas.append(
                Consumidor(
                    pid=info["pid"],
                    nome=nome,
                    memoria=rss,
                    memoria_legivel=human_bytes(rss),
                    percentagem=round(rss / total * 100, 1) if total else 0.0,
                    utilizador=(info["username"] or "").split("\\")[-1],
                    protegido=nome in PROTEGIDOS or info["pid"] in (0, 1, proprio),
                )
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    linhas.sort(key=lambda linha: linha.memoria, reverse=True)
    return linhas[:limite]


# --- Fechar programas --------------------------------------------------------

def terminar(consumidor: Consumidor, forcar: bool = False) -> tuple[bool, str]:
    """Fecha um processo. Pede primeiro com jeito; só força se for pedido."""
    if consumidor.protegido:
        return False, "Processo do sistema — fechá-lo pode deixar a máquina instável"
    try:
        processo = psutil.Process(consumidor.pid)
        if forcar:
            processo.kill()
        else:
            processo.terminate()
        processo.wait(timeout=5)
        storage.log(f"MEMÓRIA fechado '{consumidor.nome}' (pid {consumidor.pid}), "
                    f"{consumidor.memoria_legivel} ocupados")
        return True, ""
    except psutil.NoSuchProcess:
        return True, ""
    except psutil.AccessDenied:
        return False, "Sem permissões para fechar este processo"
    except psutil.TimeoutExpired:
        return False, "O programa não respondeu ao pedido para fechar"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


# --- Operações de sistema ----------------------------------------------------

def _swap_pode_ser_limpa() -> bool:
    """Só faz sentido esvaziar a swap se a RAM couber com o que lá está."""
    virtual = psutil.virtual_memory()
    swap = psutil.swap_memory()
    return swap.used > 0 and virtual.available > swap.used * 1.2


def acoes_disponiveis() -> list[AcaoMemoria]:
    if IS_MACOS:
        return [
            AcaoMemoria(
                "purge", "Libertar a cache de disco",
                "Executa o comando `purge` do macOS, que descarta a memória usada como cache "
                "de ficheiros lidos recentemente.",
                "Os ficheiros voltam a ser lidos do disco, portanto os minutos seguintes ficam "
                "mais lentos. Útil antes de uma tarefa pesada, não como hábito.",
                requires_admin=True,
            ),
        ]
    if IS_LINUX:
        return [
            AcaoMemoria(
                "drop_caches", "Libertar cache e buffers",
                "Escreve em /proc/sys/vm/drop_caches depois de sincronizar o disco. "
                "Devolve a memória usada como cache de ficheiros.",
                "A cache é reconstruída à medida que os ficheiros voltam a ser lidos. "
                "Não corrige falta de RAM — só torna o número mais bonito.",
                requires_admin=True,
            ),
            AcaoMemoria(
                "swap", "Esvaziar a swap",
                "Desliga e volta a ligar a swap, forçando o regresso à RAM do que lá estava.",
                "Só é seguro quando há RAM livre que chegue — a ferramenta verifica antes. "
                "Devolve desempenho a um servidor que esteve sob pressão de memória.",
                requires_admin=True,
                disponivel=_swap_pode_ser_limpa(),
            ),
        ]
    if IS_WINDOWS:
        return [
            AcaoMemoria(
                "conjuntos", "Reduzir o conjunto de trabalho dos programas",
                "Pede ao Windows que mova para o ficheiro de paginação as páginas que cada "
                "programa não está a usar (API EmptyWorkingSet).",
                "É o que fazem os «RAM boosters». O número de memória livre sobe, mas as "
                "páginas voltam do disco quando forem precisas — muitas vezes fica mais lento. "
                "Vale a pena para recuperar de um programa com fuga de memória, não como rotina.",
                requires_admin=False,
            ),
        ]
    return []


def executar_acao(acao: AcaoMemoria) -> tuple[bool, str]:
    antes = psutil.virtual_memory().available

    if acao.key == "purge":
        resultado = run_elevated("purge", timeout=180)
        ok, mensagem = resultado.ok, resultado.err
    elif acao.key == "drop_caches":
        resultado = run_elevated("sh -c 'sync && echo 3 > /proc/sys/vm/drop_caches'", timeout=120)
        ok, mensagem = resultado.ok, resultado.err
    elif acao.key == "swap":
        if not _swap_pode_ser_limpa():
            return False, "Não há RAM livre suficiente para receber o conteúdo da swap"
        resultado = run_elevated("sh -c 'swapoff -a && swapon -a'", timeout=300)
        ok, mensagem = resultado.ok, resultado.err
    elif acao.key == "conjuntos":
        ok, mensagem = _reduzir_conjuntos_windows()
    else:
        return False, "Operação desconhecida"

    depois = psutil.virtual_memory().available
    ganho = depois - antes
    storage.log(f"MEMÓRIA ação '{acao.key}': {'ok' if ok else mensagem}, "
                f"variação de memória disponível {human_bytes(ganho)}")
    if not ok:
        return False, mensagem or "A operação falhou"
    if ganho > 0:
        return True, f"Ficaram disponíveis mais {human_bytes(ganho)}"
    return True, "Concluído, sem variação relevante de memória disponível"


def _reduzir_conjuntos_windows() -> tuple[bool, str]:
    """Chama EmptyWorkingSet em cada processo acessível, via ctypes."""
    import ctypes  # noqa: PLC0415 - só é preciso aqui

    psapi = ctypes.WinDLL("psapi.dll")
    kernel32 = ctypes.WinDLL("kernel32.dll")
    PROCESS_SET_QUOTA, PROCESS_QUERY_INFORMATION = 0x0100, 0x0400

    tratados = 0
    for processo in psutil.process_iter(["pid", "name"]):
        pid = processo.info["pid"]
        if pid in (0, 4) or processo.info["name"] in PROTEGIDOS:
            continue
        handle = kernel32.OpenProcess(PROCESS_SET_QUOTA | PROCESS_QUERY_INFORMATION, False, pid)
        if not handle:
            continue
        try:
            if psapi.EmptyWorkingSet(handle):
                tratados += 1
        finally:
            kernel32.CloseHandle(handle)

    if tratados == 0:
        return False, "Não foi possível aceder a nenhum processo"
    return True, f"{tratados} processos tratados"
