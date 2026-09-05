"""Otimizações de sistema e gestão de serviços.

Cada otimização declara o que faz, o risco e — quando é um interruptor — como
se reverte. Nada aqui promete milagres: são ajustes concretos com efeito real.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Callable

from .. import storage
from ..platform_info import (
    IS_LINUX,
    IS_MACOS,
    IS_WINDOWS,
    is_admin,
    run,
    run_elevated,
    run_powershell,
)

BAIXO = "baixo"
MEDIO = "médio"
STATE_SECTION = "otimizacoes"

Resultado = tuple[bool, str]


@dataclass
class Tweak:
    key: str
    nome: str
    descricao: str
    beneficio: str
    risco: str = BAIXO
    tipo: str = "interruptor"          # interruptor | acao
    requires_admin: bool = False
    check: Callable[[], bool | None] | None = None
    apply_fn: Callable[[], Resultado] | None = None
    revert_fn: Callable[[], Resultado] | None = None
    so_servidor: bool = False
    so_desktop: bool = False


def _ps(script: str) -> Resultado:
    result = run_powershell(script, timeout=90)
    return result.ok, (result.err or result.out)


def _elev(command: str) -> Resultado:
    result = run_elevated(command, timeout=180)
    return result.ok, (result.err or result.out)


def _sh(command: str) -> Resultado:
    result = run(command, shell=True, timeout=90)
    return result.ok, (result.err or result.out)


# --- Windows -----------------------------------------------------------------

def _win_service_state(nome: str) -> bool | None:
    result = run_powershell(
        f"(Get-Service -Name '{nome}' -ErrorAction SilentlyContinue).StartType", timeout=25
    )
    if not result.ok or not result.out:
        return None
    return result.out.strip().lower() != "disabled"


def _win_service_tweak(key: str, nome_servico: str, nome: str, descricao: str, beneficio: str,
                       risco: str = BAIXO) -> Tweak:
    return Tweak(
        key=key,
        nome=nome,
        descricao=descricao,
        beneficio=beneficio,
        risco=risco,
        requires_admin=True,
        check=lambda: _win_service_state(nome_servico) is False,
        apply_fn=lambda: _ps(
            f"Stop-Service -Name '{nome_servico}' -Force -ErrorAction SilentlyContinue; "
            f"Set-Service -Name '{nome_servico}' -StartupType Disabled"
        ),
        revert_fn=lambda: _ps(f"Set-Service -Name '{nome_servico}' -StartupType Automatic"),
    )


def _windows_tweaks() -> list[Tweak]:
    def plano_alto_desempenho() -> bool | None:
        result = run_powershell("powercfg /getactivescheme", timeout=25)
        if not result.ok:
            return None
        return "alto desempenho" in result.out.lower() or "high performance" in result.out.lower()

    def aplicar_plano() -> Resultado:
        storage.remember(STATE_SECTION, "plano_energia", "equilibrado")
        return _ps("powercfg /setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c")

    def efeitos_visuais() -> bool | None:
        result = run_powershell(
            r"(Get-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects'"
            r" -Name VisualFXSetting -ErrorAction SilentlyContinue).VisualFXSetting",
            timeout=25,
        )
        return result.out.strip() == "2" if result.ok and result.out else None

    return [
        Tweak(
            key="plano_energia",
            nome="Plano de energia de alto desempenho",
            descricao="Impede o processador de baixar de frequência para poupar energia.",
            beneficio="Resposta mais rápida. Num portátil reduz a autonomia.",
            requires_admin=True,
            check=plano_alto_desempenho,
            apply_fn=aplicar_plano,
            revert_fn=lambda: _ps("powercfg /setactive 381b4222-f694-41f0-9685-ff5bb260df2e"),
        ),
        Tweak(
            key="efeitos_visuais",
            nome="Reduzir efeitos visuais",
            descricao="Desliga animações e sombras das janelas.",
            beneficio="Interface mais fluida em máquinas com poucos recursos.",
            check=efeitos_visuais,
            apply_fn=lambda: _ps(
                r"New-Item -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects'"
                r" -Force | Out-Null; Set-ItemProperty -Path"
                r" 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects'"
                r" -Name VisualFXSetting -Value 2"
            ),
            revert_fn=lambda: _ps(
                r"Set-ItemProperty -Path"
                r" 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects'"
                r" -Name VisualFXSetting -Value 0"
            ),
        ),
        _win_service_tweak(
            "sysmain", "SysMain", "Desativar SysMain (SuperFetch)",
            "Pré-carrega programas para memória. Útil em discos mecânicos, dispensável em SSD.",
            "Menos uso de disco e RAM em máquinas com SSD.", risco=MEDIO,
        ),
        _win_service_tweak(
            "telemetria", "DiagTrack", "Desativar telemetria (DiagTrack)",
            "Serviço que envia dados de diagnóstico para a Microsoft.",
            "Menos atividade em segundo plano e de rede.",
        ),
        _win_service_tweak(
            "fax", "Fax", "Desativar serviço de Fax",
            "Serviço de fax, sem utilidade na esmagadora maioria das máquinas.",
            "Um serviço a menos em memória.",
        ),
        _win_service_tweak(
            "registo_remoto", "RemoteRegistry", "Desativar Registo Remoto",
            "Permite editar o registo a partir da rede. Também é uma superfície de ataque.",
            "Mais segurança e menos um serviço ativo.",
        ),
        Tweak(
            key="hibernacao",
            nome="Desativar hibernação",
            descricao="Remove o ficheiro hiberfil.sys, que ocupa vários GB no disco do sistema.",
            beneficio="Liberta espaço equivalente a boa parte da RAM instalada.",
            risco=MEDIO,
            requires_admin=True,
            check=lambda: not (os.path.exists(os.path.join(os.environ.get("SystemDrive", "C:") + "\\", "hiberfil.sys"))),
            apply_fn=lambda: _ps("powercfg /hibernate off"),
            revert_fn=lambda: _ps("powercfg /hibernate on"),
        ),
        Tweak(
            key="trim",
            nome="Garantir TRIM ativo (SSD)",
            descricao="Verifica e ativa o TRIM, que mantém a velocidade de escrita dos SSD.",
            beneficio="Evita degradação de desempenho do SSD ao longo do tempo.",
            tipo="acao",
            requires_admin=True,
            apply_fn=lambda: _ps("fsutil behavior set DisableDeleteNotify 0"),
        ),
        Tweak(
            key="verificar_disco",
            nome="Verificar integridade do sistema (SFC)",
            descricao="Corre o System File Checker para reparar ficheiros de sistema corrompidos.",
            beneficio="Corrige erros que causam falhas e lentidão. Pode demorar vários minutos.",
            tipo="acao",
            risco=MEDIO,
            requires_admin=True,
            apply_fn=lambda: _ps("sfc /scannow"),
        ),
    ]


# --- macOS -------------------------------------------------------------------

def _defaults_bool(dominio: str, chave: str) -> bool | None:
    result = run(["defaults", "read", dominio, chave], timeout=15)
    if not result.ok:
        # A chave não existir significa que a definição está no valor de origem.
        if "does not exist" in (result.err or ""):
            return False
        return None
    return result.out.strip() in ("1", "true", "YES")


def _macos_tweaks() -> list[Tweak]:
    return [
        Tweak(
            key="transparencia",
            nome="Reduzir transparência",
            descricao="Desliga os efeitos de transparência do menu e do Dock.",
            beneficio="Interface mais responsiva em Macs mais antigos.",
            check=lambda: _defaults_bool("com.apple.universalaccess", "reduceTransparency"),
            apply_fn=lambda: _sh("defaults write com.apple.universalaccess reduceTransparency -bool true"),
            revert_fn=lambda: _sh("defaults write com.apple.universalaccess reduceTransparency -bool false"),
        ),
        Tweak(
            key="movimento",
            nome="Reduzir animações",
            descricao="Diminui as animações de janelas e de mudança de espaços.",
            beneficio="Sensação de rapidez ao abrir e fechar janelas.",
            check=lambda: _defaults_bool("com.apple.universalaccess", "reduceMotion"),
            apply_fn=lambda: _sh("defaults write com.apple.universalaccess reduceMotion -bool true"),
            revert_fn=lambda: _sh("defaults write com.apple.universalaccess reduceMotion -bool false"),
        ),
        Tweak(
            key="dock_rapido",
            nome="Dock sem atraso",
            descricao="Remove o atraso de aparecimento do Dock quando está oculto.",
            beneficio="O Dock responde de imediato.",
            check=lambda: run(["defaults", "read", "com.apple.dock", "autohide-delay"], timeout=10).out.strip() == "0",
            apply_fn=lambda: _sh("defaults write com.apple.dock autohide-delay -float 0 && killall Dock"),
            revert_fn=lambda: _sh("defaults delete com.apple.dock autohide-delay; killall Dock"),
        ),
        Tweak(
            key="purge",
            nome="Libertar memória inativa",
            descricao="Executa o comando `purge` do sistema.",
            beneficio="Devolve memória retida em cache. Efeito imediato mas temporário.",
            tipo="acao",
            requires_admin=True,
            apply_fn=lambda: _elev("purge"),
        ),
        Tweak(
            key="reindexar_spotlight",
            nome="Reconstruir índice do Spotlight",
            descricao="Apaga e reconstrói o índice de pesquisa.",
            beneficio="Resolve pesquisas lentas ou sem resultados. Indexa durante algumas horas.",
            tipo="acao",
            risco=MEDIO,
            requires_admin=True,
            apply_fn=lambda: _elev("mdutil -E /"),
        ),
        Tweak(
            key="manutencao",
            nome="Correr scripts de manutenção",
            descricao="Executa os scripts diários, semanais e mensais do macOS.",
            beneficio="Rotação de logs e limpezas que só correm se o Mac ficar ligado de noite.",
            tipo="acao",
            requires_admin=True,
            apply_fn=lambda: _elev("periodic daily weekly monthly"),
        ),
        Tweak(
            key="primeira_ajuda",
            nome="Primeiros socorros ao disco",
            descricao="Corre o `diskutil verifyVolume` no volume de arranque.",
            beneficio="Deteta problemas no sistema de ficheiros antes que causem perda de dados.",
            tipo="acao",
            apply_fn=lambda: _sh("diskutil verifyVolume /"),
        ),
    ]


# --- Linux -------------------------------------------------------------------

def _systemd_enabled(unidade: str) -> bool | None:
    result = run(["systemctl", "is-enabled", unidade], timeout=15)
    if result.code in (-1, -2, -3):
        return None
    return result.out.strip() == "enabled"


def _linux_service_tweak(key: str, unidade: str, nome: str, descricao: str, beneficio: str,
                         so_servidor: bool = False) -> Tweak:
    return Tweak(
        key=key,
        nome=nome,
        descricao=descricao,
        beneficio=beneficio,
        risco=MEDIO,
        requires_admin=True,
        so_servidor=so_servidor,
        check=lambda: _systemd_enabled(unidade) is False,
        apply_fn=lambda: _elev(f"systemctl disable --now {unidade}"),
        revert_fn=lambda: _elev(f"systemctl enable --now {unidade}"),
    )


def _linux_tweaks() -> list[Tweak]:
    def swappiness_atual() -> bool | None:
        try:
            with open("/proc/sys/vm/swappiness", encoding="utf-8") as handle:
                return int(handle.read().strip()) <= 20
        except (OSError, ValueError):
            return None

    def journal_limitado() -> bool | None:
        try:
            conteudo = open("/etc/systemd/journald.conf.d/99-reloadtech.conf", encoding="utf-8").read()
            return "SystemMaxUse" in conteudo
        except OSError:
            return False

    tweaks = [
        Tweak(
            key="swappiness",
            nome="Ajustar swappiness para 10",
            descricao="Faz o kernel preferir a RAM em vez da swap (valor por omissão: 60).",
            beneficio="Menos escrita em disco e melhor resposta em servidores com RAM suficiente.",
            requires_admin=True,
            check=swappiness_atual,
            apply_fn=lambda: _elev(
                "sh -c 'echo \"vm.swappiness=10\" > /etc/sysctl.d/99-reloadtech.conf && sysctl -p /etc/sysctl.d/99-reloadtech.conf'"
            ),
            revert_fn=lambda: _elev(
                "sh -c 'rm -f /etc/sysctl.d/99-reloadtech.conf && sysctl -w vm.swappiness=60'"
            ),
        ),
        Tweak(
            key="journal_limite",
            nome="Limitar registos do systemd a 200 MB",
            descricao="Define SystemMaxUse=200M no journald.",
            beneficio="Impede que os logs encham o disco — causa frequente de servidores parados.",
            requires_admin=True,
            check=journal_limitado,
            apply_fn=lambda: _elev(
                "sh -c 'mkdir -p /etc/systemd/journald.conf.d && printf \"[Journal]\\nSystemMaxUse=200M\\n\" "
                "> /etc/systemd/journald.conf.d/99-reloadtech.conf && systemctl restart systemd-journald'"
            ),
            revert_fn=lambda: _elev(
                "sh -c 'rm -f /etc/systemd/journald.conf.d/99-reloadtech.conf && systemctl restart systemd-journald'"
            ),
        ),
        Tweak(
            key="fstrim",
            nome="Ativar TRIM semanal (SSD)",
            descricao="Ativa o temporizador fstrim.timer do systemd.",
            beneficio="Mantém o desempenho de escrita do SSD ao longo do tempo.",
            requires_admin=True,
            check=lambda: _systemd_enabled("fstrim.timer") is True,
            apply_fn=lambda: _elev("systemctl enable --now fstrim.timer"),
            revert_fn=lambda: _elev("systemctl disable --now fstrim.timer"),
        ),
        Tweak(
            key="fstrim_agora",
            nome="Executar TRIM agora",
            descricao="Corre `fstrim -av` em todos os sistemas de ficheiros suportados.",
            beneficio="Recupera desempenho de escrita imediatamente.",
            tipo="acao",
            requires_admin=True,
            apply_fn=lambda: _elev("fstrim -av"),
        ),
        Tweak(
            key="pacotes_orfaos",
            nome="Remover pacotes órfãos",
            descricao="Corre `apt-get autoremove` (ou o equivalente do sistema).",
            beneficio="Liberta espaço ocupado por dependências que já ninguém usa.",
            tipo="acao",
            risco=MEDIO,
            requires_admin=True,
            apply_fn=lambda: _elev(
                "sh -c 'command -v apt-get >/dev/null && apt-get -y autoremove || "
                "(command -v dnf >/dev/null && dnf -y autoremove)'"
            ),
        ),
    ]

    servicos = [
        ("bluetooth", "bluetooth.service", "Desativar Bluetooth",
         "O serviço de Bluetooth raramente é usado num servidor.", "Menos um serviço ativo.", True),
        ("cups", "cups.service", "Desativar servidor de impressão (CUPS)",
         "Sistema de impressão. Desnecessário se a máquina não imprime.", "Menos memória e portas abertas.", True),
        ("avahi", "avahi-daemon.service", "Desativar Avahi (mDNS)",
         "Descoberta de dispositivos na rede local.", "Menos tráfego e superfície de rede.", True),
        ("modemmanager", "ModemManager.service", "Desativar ModemManager",
         "Gestão de modems móveis, sem uso em máquinas fixas.", "Menos um serviço no arranque.", True),
    ]
    for key, unidade, nome, descricao, beneficio, servidor in servicos:
        if _systemd_enabled(unidade) is not None:
            tweaks.append(_linux_service_tweak(key, unidade, nome, descricao, beneficio, servidor))
    return tweaks


# --- API pública -------------------------------------------------------------

def available_tweaks() -> list[Tweak]:
    if IS_WINDOWS:
        return _windows_tweaks()
    if IS_MACOS:
        return _macos_tweaks()
    if IS_LINUX:
        return _linux_tweaks()
    return []


def state_of(tweak: Tweak) -> bool | None:
    """True = já aplicado, False = por aplicar, None = não foi possível determinar."""
    if tweak.tipo == "acao" or tweak.check is None:
        return None
    try:
        return tweak.check()
    except Exception:  # noqa: BLE001
        return None


def apply(tweak: Tweak) -> Resultado:
    if tweak.requires_admin and IS_WINDOWS and not is_admin():
        return False, "Requer executar a aplicação como administrador"
    if tweak.apply_fn is None:
        return False, "Otimização sem ação definida"
    ok, mensagem = tweak.apply_fn()
    storage.log(f"OTIMIZAÇÃO aplicar '{tweak.key}': {'ok' if ok else mensagem}")
    return ok, mensagem


def revert(tweak: Tweak) -> Resultado:
    if tweak.revert_fn is None:
        return False, "Esta operação não é reversível automaticamente"
    if tweak.requires_admin and IS_WINDOWS and not is_admin():
        return False, "Requer executar a aplicação como administrador"
    ok, mensagem = tweak.revert_fn()
    storage.log(f"OTIMIZAÇÃO reverter '{tweak.key}': {'ok' if ok else mensagem}")
    return ok, mensagem
