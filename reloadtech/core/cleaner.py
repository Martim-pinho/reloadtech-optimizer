"""Limpeza de ficheiros descartáveis.

Regras que a ferramenta segue, por decisão de desenho:
  * Nada é apagado sem uma análise prévia mostrada ao utilizador.
  * Só se apaga o *conteúdo* de pastas conhecidas, nunca a pasta em si.
  * Documentos, transferências e dados de utilizador nunca são tocados.
"""
from __future__ import annotations

import os
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

from .. import storage
from ..platform_info import (
    IS_LINUX,
    IS_MACOS,
    IS_WINDOWS,
    human_bytes,
    is_admin,
    run,
    run_elevated,
    run_powershell,
)

SAFE = "seguro"
MODERATE = "moderado"


@dataclass
class CleanTarget:
    key: str
    nome: str
    descricao: str
    risco: str = SAFE
    paths: list[Path] = field(default_factory=list)
    requires_admin: bool = False
    min_age_days: int | None = None
    scan_command: str | None = None
    clean_command: str | None = None
    elevated_command: bool = False


@dataclass
class ScanResult:
    target: CleanTarget
    bytes: int = 0
    files: int = 0
    error: str | None = None

    @property
    def readable(self) -> str:
        return human_bytes(self.bytes)


# --- Definição dos alvos por sistema -----------------------------------------

def _env_path(*parts: str) -> Path | None:
    variable, *rest = parts
    base = os.environ.get(variable)
    if not base:
        return None
    return Path(base).joinpath(*rest)


def _windows_targets() -> list[CleanTarget]:
    local = os.environ.get("LOCALAPPDATA", "")
    targets = [
        CleanTarget(
            "temp_utilizador",
            "Ficheiros temporários do utilizador",
            "Pasta TEMP da conta atual. Ficheiros de trabalho que os programas deixaram para trás.",
            paths=[p for p in [_env_path("TEMP"), _env_path("TMP")] if p],
        ),
        CleanTarget(
            "temp_windows",
            "Ficheiros temporários do Windows",
            "C:\\Windows\\Temp — temporários do sistema.",
            requires_admin=True,
            paths=[Path(os.environ.get("SystemRoot", "C:\\Windows")) / "Temp"],
        ),
        CleanTarget(
            "prefetch",
            "Prefetch",
            "Cache de pré-carregamento. É reconstruída automaticamente.",
            risco=MODERATE,
            requires_admin=True,
            paths=[Path(os.environ.get("SystemRoot", "C:\\Windows")) / "Prefetch"],
        ),
        CleanTarget(
            "windows_update",
            "Cache do Windows Update",
            "Instaladores de atualizações já aplicadas.",
            risco=MODERATE,
            requires_admin=True,
            paths=[Path(os.environ.get("SystemRoot", "C:\\Windows")) / "SoftwareDistribution" / "Download"],
        ),
        CleanTarget(
            "relatorios_erro",
            "Relatórios de erro e despejos de memória",
            "Ficheiros de diagnóstico de falhas antigas.",
            paths=[p for p in [_env_path("LOCALAPPDATA", "CrashDumps")] if p],
        ),
        CleanTarget(
            "miniaturas",
            "Cache de miniaturas",
            "Pré-visualizações de imagens. O Explorador recria-as conforme necessário.",
            paths=[Path(local) / "Microsoft" / "Windows" / "Explorer"] if local else [],
        ),
        CleanTarget(
            "reciclagem",
            "Reciclagem",
            "Esvazia a reciclagem. Atenção: os ficheiros deixam de ser recuperáveis.",
            risco=MODERATE,
            scan_command="(Get-ChildItem -Path 'C:\\$Recycle.Bin' -Recurse -Force -ErrorAction SilentlyContinue "
            "| Measure-Object -Property Length -Sum).Sum",
            clean_command="Clear-RecycleBin -Force -ErrorAction SilentlyContinue",
        ),
    ]

    if local:
        browsers = {
            "cache_chrome": ("Google Chrome", Path(local) / "Google" / "Chrome" / "User Data" / "Default" / "Cache"),
            "cache_edge": ("Microsoft Edge", Path(local) / "Microsoft" / "Edge" / "User Data" / "Default" / "Cache"),
        }
        for key, (nome, path) in browsers.items():
            targets.append(
                CleanTarget(
                    key,
                    f"Cache do {nome}",
                    "Páginas e imagens guardadas. As palavras-passe e o histórico não são afetados.",
                    paths=[path],
                )
            )
        appdata = os.environ.get("APPDATA")
        if appdata:
            firefox = Path(appdata) / "Mozilla" / "Firefox" / "Profiles"
            if firefox.exists():
                targets.append(
                    CleanTarget(
                        "cache_firefox",
                        "Cache do Firefox",
                        "Cache dos perfis do Firefox.",
                        paths=list(firefox.glob("*/cache2")),
                    )
                )
    return targets


def _macos_targets() -> list[CleanTarget]:
    home = Path.home()
    return [
        CleanTarget(
            "cache_utilizador",
            "Caches do utilizador",
            "~/Library/Caches — dados temporários das aplicações.",
            paths=[home / "Library" / "Caches"],
        ),
        CleanTarget(
            "logs_utilizador",
            "Registos de aplicações",
            "~/Library/Logs — ficheiros de log antigos.",
            paths=[home / "Library" / "Logs"],
            min_age_days=7,
        ),
        CleanTarget(
            "lixo",
            "Lixo",
            "Esvazia o Lixo. Atenção: os ficheiros deixam de ser recuperáveis.",
            risco=MODERATE,
            paths=[home / ".Trash"],
        ),
        CleanTarget(
            "cache_safari",
            "Cache do Safari",
            "Cache do navegador. Favoritos e palavras-passe não são afetados.",
            paths=[home / "Library" / "Caches" / "com.apple.Safari"],
        ),
        CleanTarget(
            "cache_chrome_mac",
            "Cache do Google Chrome",
            "Cache do navegador. Favoritos e palavras-passe não são afetados.",
            paths=[home / "Library" / "Caches" / "Google" / "Chrome"],
        ),
        CleanTarget(
            "xcode",
            "Dados de compilação do Xcode",
            "DerivedData e caches de compilação. Só relevante em máquinas de desenvolvimento.",
            paths=[home / "Library" / "Developer" / "Xcode" / "DerivedData"],
        ),
        CleanTarget(
            "homebrew",
            "Cache do Homebrew",
            "Pacotes descarregados pelo Homebrew.",
            paths=[home / "Library" / "Caches" / "Homebrew"],
        ),
        CleanTarget(
            "logs_sistema",
            "Registos do sistema",
            "/private/var/log — logs antigos do macOS.",
            risco=MODERATE,
            requires_admin=True,
            min_age_days=14,
            paths=[Path("/private/var/log")],
        ),
    ]


def _linux_targets() -> list[CleanTarget]:
    home = Path.home()
    targets = [
        CleanTarget(
            "cache_utilizador",
            "Cache do utilizador",
            "~/.cache — dados temporários das aplicações.",
            paths=[home / ".cache"],
        ),
        CleanTarget(
            "miniaturas",
            "Miniaturas",
            "Pré-visualizações de imagens geradas pelo ambiente de trabalho.",
            paths=[home / ".cache" / "thumbnails", home / ".thumbnails"],
        ),
        CleanTarget(
            "lixo",
            "Lixo",
            "Esvazia o lixo do utilizador. Atenção: deixa de ser recuperável.",
            risco=MODERATE,
            paths=[home / ".local" / "share" / "Trash" / "files",
                   home / ".local" / "share" / "Trash" / "info"],
        ),
        CleanTarget(
            "tmp",
            "/tmp antigo",
            "Ficheiros em /tmp com mais de 7 dias.",
            risco=MODERATE,
            min_age_days=7,
            paths=[Path("/tmp")],
        ),
    ]

    if Path("/var/cache/apt/archives").exists():
        targets.append(
            CleanTarget(
                "apt",
                "Cache de pacotes APT",
                "Pacotes .deb já instalados que continuam guardados.",
                requires_admin=True,
                scan_command="du -sb /var/cache/apt/archives 2>/dev/null | cut -f1",
                clean_command="apt-get clean",
                elevated_command=True,
            )
        )
    if Path("/var/cache/dnf").exists() or Path("/var/cache/yum").exists():
        targets.append(
            CleanTarget(
                "dnf",
                "Cache de pacotes DNF/YUM",
                "Metadados e pacotes descarregados.",
                requires_admin=True,
                scan_command="du -sb /var/cache/dnf /var/cache/yum 2>/dev/null | awk '{s+=$1} END {print s}'",
                clean_command="dnf clean all || yum clean all",
                elevated_command=True,
            )
        )
    if Path("/var/log/journal").exists():
        targets.append(
            CleanTarget(
                "journal",
                "Registos do systemd (journal)",
                "Reduz o journal para os últimos 7 dias.",
                risco=MODERATE,
                requires_admin=True,
                scan_command="journalctl --disk-usage | grep -oE '[0-9.]+[KMGT]?' | head -1",
                clean_command="journalctl --vacuum-time=7d",
                elevated_command=True,
            )
        )
    return targets


def available_targets() -> list[CleanTarget]:
    if IS_WINDOWS:
        targets = _windows_targets()
    elif IS_MACOS:
        targets = _macos_targets()
    elif IS_LINUX:
        targets = _linux_targets()
    else:
        targets = []
    # Mantém apenas alvos que existem mesmo nesta máquina
    return [
        target
        for target in targets
        if target.scan_command or any(path and path.exists() for path in target.paths)
    ]


# --- Análise -----------------------------------------------------------------

def _is_protected(path: Path) -> bool:
    """Barreira final: recusa apagar raízes de sistema ou a pasta pessoal."""
    resolved = Path(os.path.abspath(str(path)))
    protegidos = {
        Path.home(),
        Path(resolved.anchor) if resolved.anchor else Path("/"),
        Path("/"),
        Path("/usr"), Path("/etc"), Path("/bin"), Path("/System"), Path("/Applications"),
        Path.home() / "Documents", Path.home() / "Desktop", Path.home() / "Downloads",
    }
    return resolved in protegidos


def _too_recent(path: Path, min_age_days: int | None) -> bool:
    if min_age_days is None:
        return False
    try:
        return (time.time() - path.stat().st_mtime) < min_age_days * 86400
    except OSError:
        return True


def scan_target(target: CleanTarget) -> ScanResult:
    result = ScanResult(target=target)

    if target.requires_admin and not is_admin() and not (IS_MACOS or IS_LINUX):
        result.error = "Requer privilégios de administrador"
        return result

    if target.scan_command:
        command = run_powershell(target.scan_command) if IS_WINDOWS else run(target.scan_command, shell=True)
        raw = (command.out or "").strip()
        result.bytes = _parse_size(raw)
        return result

    for path in target.paths:
        if not path or not path.exists() or _is_protected(path):
            continue
        for root, _dirs, files in os.walk(path, onerror=lambda _e: None):
            for name in files:
                entry = Path(root) / name
                try:
                    if _too_recent(entry, target.min_age_days):
                        continue
                    result.bytes += entry.lstat().st_size
                    result.files += 1
                except OSError:
                    continue
    return result


def _parse_size(raw: str) -> int:
    """Aceita '1234' ou '512.0M' (formato do journalctl)."""
    raw = raw.strip()
    if not raw:
        return 0
    if raw.isdigit():
        return int(raw)
    unidades = {"K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}
    sufixo = raw[-1].upper()
    if sufixo in unidades:
        try:
            return int(float(raw[:-1]) * unidades[sufixo])
        except ValueError:
            return 0
    try:
        return int(float(raw))
    except ValueError:
        return 0


def scan(targets: list[CleanTarget] | None = None, progress=None) -> list[ScanResult]:
    targets = targets if targets is not None else available_targets()
    results = []
    for index, target in enumerate(targets):
        if progress:
            progress(int(index / max(1, len(targets)) * 100), f"A analisar: {target.nome}")
        results.append(scan_target(target))
    if progress:
        progress(100, "Análise concluída")
    return results


# --- Limpeza -----------------------------------------------------------------

def clean_target(target: CleanTarget) -> ScanResult:
    result = ScanResult(target=target)

    if target.clean_command:
        antes = scan_target(target).bytes
        command = (
            run_elevated(target.clean_command)
            if target.elevated_command
            else (run_powershell(target.clean_command) if IS_WINDOWS else run(target.clean_command, shell=True))
        )
        if not command.ok:
            result.error = command.err or "Falhou"
        else:
            result.bytes = max(0, antes - scan_target(target).bytes)
        storage.log(f"LIMPEZA comando '{target.key}': {'ok' if command.ok else command.err}")
        return result

    for path in target.paths:
        if not path or not path.exists() or _is_protected(path):
            continue
        for entry in path.iterdir():
            try:
                if _too_recent(entry, target.min_age_days):
                    continue
                if entry.is_dir() and not entry.is_symlink():
                    size = sum(f.lstat().st_size for f in entry.rglob("*") if f.is_file())
                    shutil.rmtree(entry, ignore_errors=True)
                    if not entry.exists():
                        result.bytes += size
                        result.files += 1
                else:
                    size = entry.lstat().st_size
                    entry.unlink()
                    result.bytes += size
                    result.files += 1
            except (OSError, PermissionError):
                # Ficheiro em uso — normal, ignora-se sem alarmar o utilizador
                continue

    storage.log(f"LIMPEZA '{target.key}': {result.files} itens, {human_bytes(result.bytes)} libertados")
    return result


def clean(targets: list[CleanTarget], progress=None) -> list[ScanResult]:
    results = []
    for index, target in enumerate(targets):
        if progress:
            progress(int(index / max(1, len(targets)) * 100), f"A limpar: {target.nome}")
        results.append(clean_target(target))
    if progress:
        progress(100, "Limpeza concluída")
    return results
