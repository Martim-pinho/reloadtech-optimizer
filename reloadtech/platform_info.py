"""Deteção de sistema, execução de comandos e helpers partilhados."""
from __future__ import annotations

import ctypes
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass

IS_WINDOWS = sys.platform.startswith("win")
IS_MACOS = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")

APP_NAME = "ReloadTech Optimizer"
APP_VERSION = "1.0.0"
BRAND = "ReloadTech"

# Evita janelas de consola a piscar no Windows
_NO_WINDOW = 0x08000000 if IS_WINDOWS else 0


@dataclass
class CommandResult:
    code: int
    out: str
    err: str

    @property
    def ok(self) -> bool:
        return self.code == 0


def run(cmd: list[str] | str, timeout: int = 30, shell: bool = False) -> CommandResult:
    """Executa um comando e devolve o resultado sem nunca levantar exceção."""
    try:
        proc = subprocess.run(
            cmd,
            shell=shell,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=_NO_WINDOW,
            errors="replace",
        )
        return CommandResult(proc.returncode, (proc.stdout or "").strip(), (proc.stderr or "").strip())
    except subprocess.TimeoutExpired:
        return CommandResult(-1, "", f"Tempo esgotado ({timeout}s)")
    except FileNotFoundError:
        return CommandResult(-2, "", "Comando não encontrado")
    except Exception as exc:  # noqa: BLE001 - diagnóstico nunca deve rebentar a app
        return CommandResult(-3, "", str(exc))


def run_powershell(script: str, timeout: int = 60) -> CommandResult:
    if not IS_WINDOWS:
        return CommandResult(-2, "", "PowerShell só está disponível no Windows")
    return run(
        ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script],
        timeout=timeout,
    )


def powershell_json(script: str, timeout: int = 60):
    """Corre PowerShell e devolve JSON já convertido (lista, dict ou None)."""
    result = run_powershell(f"{script} | ConvertTo-Json -Depth 4 -Compress", timeout=timeout)
    if not result.ok or not result.out:
        return None
    try:
        data = json.loads(result.out)
    except json.JSONDecodeError:
        return None
    return data


def is_admin() -> bool:
    """True se o processo tem privilégios administrativos."""
    if IS_WINDOWS:
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:  # noqa: BLE001
            return False
    try:
        return os.geteuid() == 0
    except AttributeError:
        return False


def run_elevated(command: str, timeout: int = 120) -> CommandResult:
    """Corre um comando com privilégios, pedindo autorização ao utilizador.

    No macOS usa o diálogo nativo do sistema. No Windows, se já corremos como
    administrador executa diretamente; caso contrário devolve erro explícito
    (a app deve pedir para reabrir como administrador, nunca elevar às escondidas).
    """
    if IS_MACOS:
        escaped = command.replace("\\", "\\\\").replace('"', '\\"')
        return run(
            ["osascript", "-e", f'do shell script "{escaped}" with administrator privileges'],
            timeout=timeout,
        )
    if IS_WINDOWS:
        if not is_admin():
            return CommandResult(-4, "", "Requer executar a aplicação como administrador")
        return run_powershell(command, timeout=timeout)
    if not is_admin():
        return CommandResult(-4, "", "Requer privilégios de root")
    return run(command, timeout=timeout, shell=True)


def human_bytes(num: float) -> str:
    """1536 -> '1,5 KB'. Usa vírgula decimal (pt-PT)."""
    if num is None:
        return "n/d"
    num = float(num)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(num) < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(num)} B"
            return f"{num:.1f}".replace(".", ",") + f" {unit}"
        num /= 1024
    return f"{num:.1f} TB"


def which(name: str) -> str | None:
    return shutil.which(name)


def os_label() -> str:
    if IS_WINDOWS:
        return "Windows"
    if IS_MACOS:
        return "macOS"
    return "Linux"


def reduced_motion() -> bool:
    """True se o sistema pedir menos movimento.

    Uma app que ignora esta definição é uma app que não presta atenção. Custa
    uma leitura e evita enjoar quem a ativou por necessidade.
    """
    try:
        if IS_MACOS:
            result = run(["defaults", "read", "com.apple.universalaccess", "reduceMotion"], timeout=8)
            return result.ok and result.out.strip() in ("1", "true")
        if IS_WINDOWS:
            data = powershell_json(
                r"(Get-ItemProperty -Path 'HKCU:\Control Panel\Desktop\WindowMetrics'"
                r" -Name MinAnimate -ErrorAction SilentlyContinue).MinAnimate"
            )
            return str(data).strip() == "0"
        if IS_LINUX:
            result = run(["gsettings", "get", "org.gnome.desktop.interface", "enable-animations"], timeout=8)
            return result.ok and result.out.strip() == "false"
    except Exception:  # noqa: BLE001
        pass
    return False
