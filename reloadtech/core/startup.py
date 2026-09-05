"""Programas e serviços que arrancam com o sistema.

Desativar é sempre reversível: o valor original é guardado em `storage` antes
de qualquer alteração, e `enable()` repõe exatamente o que estava lá.
"""
from __future__ import annotations

import json
import os
import plistlib
import re
from dataclasses import dataclass
from pathlib import Path

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

STATE_SECTION = "arranque"


@dataclass
class StartupItem:
    key: str
    nome: str
    comando: str
    origem: str          # onde está definido, em linguagem humana
    tipo: str            # registo | pasta | launchagent | autostart | systemd
    ativo: bool = True
    escopo: str = "utilizador"
    requires_admin: bool = False
    referencia: str = ""  # caminho ou chave interna usada para reverter


# --- Windows -----------------------------------------------------------------

_WIN_RUN_KEYS = [
    ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Run", "utilizador"),
    ("HKLM", r"Software\Microsoft\Windows\CurrentVersion\Run", "sistema"),
    ("HKLM", r"Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Run", "sistema"),
]


def _windows_items() -> list[StartupItem]:
    import winreg  # noqa: PLC0415 - só existe no Windows

    roots = {"HKCU": winreg.HKEY_CURRENT_USER, "HKLM": winreg.HKEY_LOCAL_MACHINE}
    items: list[StartupItem] = []

    for root_name, subkey, escopo in _WIN_RUN_KEYS:
        try:
            with winreg.OpenKey(roots[root_name], subkey) as key:
                index = 0
                while True:
                    try:
                        nome, valor, _tipo = winreg.EnumValue(key, index)
                    except OSError:
                        break
                    index += 1
                    items.append(
                        StartupItem(
                            key=f"reg::{root_name}::{subkey}::{nome}",
                            nome=nome,
                            comando=str(valor),
                            origem=f"Registo ({root_name})",
                            tipo="registo",
                            ativo=True,
                            escopo=escopo,
                            requires_admin=(root_name == "HKLM"),
                            referencia=f"{root_name}|{subkey}|{nome}",
                        )
                    )
        except FileNotFoundError:
            continue
        except OSError:
            continue

    # Pastas "Arranque"
    folders = []
    appdata = os.environ.get("APPDATA")
    programdata = os.environ.get("ProgramData")
    if appdata:
        folders.append((Path(appdata) / "Microsoft/Windows/Start Menu/Programs/Startup", "utilizador", False))
    if programdata:
        folders.append((Path(programdata) / "Microsoft/Windows/Start Menu/Programs/StartUp", "sistema", True))

    for folder, escopo, admin in folders:
        if not folder.exists():
            continue
        disabled = folder / "Desativados_ReloadTech"
        for entry in list(folder.glob("*")) + (list(disabled.glob("*")) if disabled.exists() else []):
            if entry.is_dir() or entry.name.lower() == "desktop.ini":
                continue
            items.append(
                StartupItem(
                    key=f"folder::{entry}",
                    nome=entry.stem,
                    comando=str(entry),
                    origem="Pasta Arranque",
                    tipo="pasta",
                    ativo=entry.parent.name != "Desativados_ReloadTech",
                    escopo=escopo,
                    requires_admin=admin,
                    referencia=str(entry),
                )
            )

    # Itens já desativados por nós (guardados no estado)
    for key, saved in storage.load_state().get(STATE_SECTION, {}).items():
        if key.startswith("reg::") and not any(item.key == key for item in items):
            items.append(
                StartupItem(
                    key=key,
                    nome=saved.get("nome", key.split("::")[-1]),
                    comando=saved.get("valor", ""),
                    origem=f"Registo ({saved.get('root', '')})",
                    tipo="registo",
                    ativo=False,
                    escopo=saved.get("escopo", "utilizador"),
                    requires_admin=saved.get("root") == "HKLM",
                    referencia=saved.get("referencia", ""),
                )
            )
    return items


def _windows_set(item: StartupItem, ativar: bool) -> tuple[bool, str]:
    import winreg  # noqa: PLC0415

    if item.tipo == "pasta":
        entry = Path(item.referencia)
        folder = entry.parent
        if ativar:
            destino = folder.parent / entry.name if folder.name == "Desativados_ReloadTech" else entry
        else:
            desativados = folder / "Desativados_ReloadTech"
            desativados.mkdir(exist_ok=True)
            destino = desativados / entry.name
        try:
            entry.rename(destino)
            return True, ""
        except OSError as exc:
            return False, str(exc)

    root_name, subkey, nome = item.referencia.split("|", 2)
    roots = {"HKCU": winreg.HKEY_CURRENT_USER, "HKLM": winreg.HKEY_LOCAL_MACHINE}
    try:
        if ativar:
            saved = storage.recall(STATE_SECTION, item.key)
            if not saved:
                return False, "Não há cópia do valor original para repor"
            with winreg.OpenKey(roots[root_name], subkey, 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, nome, 0, winreg.REG_SZ, saved["valor"])
            storage.forget(STATE_SECTION, item.key)
        else:
            storage.remember(
                STATE_SECTION,
                item.key,
                {"nome": nome, "valor": item.comando, "root": root_name,
                 "referencia": item.referencia, "escopo": item.escopo},
            )
            with winreg.OpenKey(roots[root_name], subkey, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, nome)
        return True, ""
    except PermissionError:
        return False, "Requer executar como administrador"
    except OSError as exc:
        return False, str(exc)


# --- macOS -------------------------------------------------------------------

def _macos_items() -> list[StartupItem]:
    items: list[StartupItem] = []
    locais = [
        (Path.home() / "Library" / "LaunchAgents", "utilizador", False),
        (Path("/Library/LaunchAgents"), "sistema", True),
        (Path("/Library/LaunchDaemons"), "sistema", True),
    ]
    desativados = storage.load_state().get(STATE_SECTION, {})

    for pasta, escopo, admin in locais:
        if not pasta.exists():
            continue
        for plist in sorted(pasta.glob("*.plist")):
            label = plist.stem
            comando = ""
            try:
                with open(plist, "rb") as handle:
                    dados = plistlib.load(handle)
                programa = dados.get("ProgramArguments") or dados.get("Program")
                comando = " ".join(programa) if isinstance(programa, list) else str(programa or "")
                if dados.get("Disabled"):
                    continue
            except Exception:  # noqa: BLE001 - plists corrompidos existem
                comando = str(plist)
            key = f"launch::{plist}"
            items.append(
                StartupItem(
                    key=key,
                    nome=label,
                    comando=comando,
                    origem=str(pasta),
                    tipo="launchagent",
                    ativo=key not in desativados,
                    escopo=escopo,
                    requires_admin=admin,
                    referencia=str(plist),
                )
            )

    # Itens de início de sessão (Preferências > Utilizadores)
    result = run(
        ["osascript", "-e", 'tell application "System Events" to get the name of every login item'],
        timeout=20,
    )
    if result.ok and result.out:
        for nome in [n.strip() for n in result.out.split(",") if n.strip()]:
            items.append(
                StartupItem(
                    key=f"loginitem::{nome}",
                    nome=nome,
                    comando="Item de início de sessão",
                    origem="Itens de início de sessão",
                    tipo="loginitem",
                    ativo=True,
                    escopo="utilizador",
                    referencia=nome,
                )
            )
    return items


def _macos_set(item: StartupItem, ativar: bool) -> tuple[bool, str]:
    if item.tipo == "loginitem":
        if ativar:
            return False, "Reativar itens de início de sessão tem de ser feito nas Definições do Sistema"
        script = f'tell application "System Events" to delete login item "{item.referencia}"'
        result = run(["osascript", "-e", script], timeout=20)
        return result.ok, result.err

    plist = Path(item.referencia)
    comando = f"launchctl {'load' if ativar else 'unload'} -w {plist}"
    result = run_elevated(comando) if item.requires_admin else run(comando, shell=True)
    if not result.ok and result.code not in (0,):
        return False, result.err or "Falhou"
    if ativar:
        storage.forget(STATE_SECTION, item.key)
    else:
        storage.remember(STATE_SECTION, item.key, {"plist": str(plist), "nome": item.nome})
    return True, ""


# --- Linux -------------------------------------------------------------------

def _linux_items() -> list[StartupItem]:
    items: list[StartupItem] = []

    autostart = Path.home() / ".config" / "autostart"
    if autostart.exists():
        for desktop in sorted(autostart.glob("*.desktop")):
            conteudo = ""
            try:
                conteudo = desktop.read_text(encoding="utf-8", errors="replace")
            except OSError:
                pass
            nome = re.search(r"^Name=(.+)$", conteudo, re.MULTILINE)
            comando = re.search(r"^Exec=(.+)$", conteudo, re.MULTILINE)
            oculto = re.search(r"^Hidden=true$", conteudo, re.MULTILINE | re.IGNORECASE)
            items.append(
                StartupItem(
                    key=f"autostart::{desktop}",
                    nome=nome.group(1).strip() if nome else desktop.stem,
                    comando=comando.group(1).strip() if comando else "",
                    origem="~/.config/autostart",
                    tipo="autostart",
                    ativo=oculto is None,
                    escopo="utilizador",
                    referencia=str(desktop),
                )
            )

    # Serviços systemd ativados no arranque — o que realmente pesa num servidor
    result = run(
        ["systemctl", "list-unit-files", "--type=service", "--state=enabled", "--no-legend", "--no-pager"],
        timeout=25,
    )
    if result.ok:
        for linha in result.out.splitlines():
            partes = linha.split()
            if not partes:
                continue
            unidade = partes[0]
            descricao = run(["systemctl", "show", unidade, "-p", "Description", "--value"], timeout=10)
            items.append(
                StartupItem(
                    key=f"systemd::{unidade}",
                    nome=unidade,
                    comando=descricao.out if descricao.ok else "",
                    origem="systemd (sistema)",
                    tipo="systemd",
                    ativo=True,
                    escopo="sistema",
                    requires_admin=True,
                    referencia=unidade,
                )
            )

    desativados = storage.load_state().get(STATE_SECTION, {})
    for key, saved in desativados.items():
        if key.startswith("systemd::") and not any(item.key == key for item in items):
            items.append(
                StartupItem(
                    key=key,
                    nome=saved.get("nome", key.split("::")[-1]),
                    comando=saved.get("descricao", ""),
                    origem="systemd (sistema)",
                    tipo="systemd",
                    ativo=False,
                    escopo="sistema",
                    requires_admin=True,
                    referencia=saved.get("unidade", ""),
                )
            )
    return items


def _linux_set(item: StartupItem, ativar: bool) -> tuple[bool, str]:
    if item.tipo == "autostart":
        desktop = Path(item.referencia)
        try:
            conteudo = desktop.read_text(encoding="utf-8", errors="replace")
            conteudo = re.sub(r"^Hidden=.*$\n?", "", conteudo, flags=re.MULTILINE | re.IGNORECASE)
            if not ativar:
                conteudo = conteudo.rstrip("\n") + "\nHidden=true\n"
            desktop.write_text(conteudo, encoding="utf-8")
            return True, ""
        except OSError as exc:
            return False, str(exc)

    unidade = item.referencia
    acao = "enable" if ativar else "disable"
    comando = f"systemctl {acao} {unidade}"
    result = run_elevated(comando) if not is_admin() else run(comando, shell=True)
    if not result.ok:
        return False, result.err or "Falhou"
    if ativar:
        storage.forget(STATE_SECTION, item.key)
    else:
        storage.remember(STATE_SECTION, item.key, {"unidade": unidade, "nome": item.nome, "descricao": item.comando})
    return True, ""


# --- API pública -------------------------------------------------------------

# Serviços que nunca devem ser sugeridos para desativar num servidor.
PROTEGIDOS = {
    "ssh.service", "sshd.service", "systemd-networkd.service", "networking.service",
    "NetworkManager.service", "systemd-resolved.service", "systemd-journald.service",
    "dbus.service", "cron.service", "crond.service", "systemd-logind.service",
}


def list_items() -> list[StartupItem]:
    try:
        if IS_WINDOWS:
            items = _windows_items()
        elif IS_MACOS:
            items = _macos_items()
        elif IS_LINUX:
            items = _linux_items()
        else:
            items = []
    except Exception as exc:  # noqa: BLE001
        storage.log(f"ARRANQUE erro a listar: {exc}")
        return []
    return sorted(items, key=lambda item: (not item.ativo, item.nome.lower()))


def is_protected(item: StartupItem) -> bool:
    return item.nome in PROTEGIDOS or item.referencia in PROTEGIDOS


def set_enabled(item: StartupItem, ativar: bool) -> tuple[bool, str]:
    if not ativar and is_protected(item):
        return False, "Serviço essencial — desativá-lo pode deixar a máquina inacessível"
    if IS_WINDOWS:
        ok, erro = _windows_set(item, ativar)
    elif IS_MACOS:
        ok, erro = _macos_set(item, ativar)
    elif IS_LINUX:
        ok, erro = _linux_set(item, ativar)
    else:
        ok, erro = False, "Sistema não suportado"
    storage.log(f"ARRANQUE {'ativar' if ativar else 'desativar'} '{item.nome}': {'ok' if ok else erro}")
    return ok, erro
