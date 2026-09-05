"""Programas instalados: o que ocupa espaço e o que já não é preciso.

É aqui que costuma estar o espaço a sério. Limpar caches devolve alguns GB;
desinstalar três programas que ninguém abre há dois anos devolve dezenas.
"""
from __future__ import annotations

import json
import os
import plistlib
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .. import storage
from ..platform_info import (
    IS_LINUX,
    IS_MACOS,
    IS_WINDOWS,
    human_bytes,
    run,
    run_elevated,
    powershell_json,
)


@dataclass
class Programa:
    nome: str
    versao: str = ""
    editor: str = ""
    tamanho: int = 0
    instalado_em: str = ""
    ultimo_uso: str = ""
    localizacao: str = ""
    comando_remocao: str = ""
    identificador: str = ""
    do_sistema: bool = False

    @property
    def tamanho_legivel(self) -> str:
        return human_bytes(self.tamanho) if self.tamanho else "—"


# --- Windows -----------------------------------------------------------------

_CHAVES_WINDOWS = [
    ("HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ("HKLM", r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
    ("HKCU", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
]


def _windows() -> list[Programa]:
    import winreg  # noqa: PLC0415 - só existe no Windows

    raizes = {"HKLM": winreg.HKEY_LOCAL_MACHINE, "HKCU": winreg.HKEY_CURRENT_USER}
    programas: list[Programa] = []
    vistos: set[str] = set()

    for nome_raiz, subchave in _CHAVES_WINDOWS:
        try:
            with winreg.OpenKey(raizes[nome_raiz], subchave) as chave:
                for indice in range(winreg.QueryInfoKey(chave)[0]):
                    try:
                        nome_sub = winreg.EnumKey(chave, indice)
                        with winreg.OpenKey(chave, nome_sub) as entrada:
                            def ler(campo, padrao=""):
                                try:
                                    return winreg.QueryValueEx(entrada, campo)[0]
                                except OSError:
                                    return padrao

                            nome = str(ler("DisplayName")).strip()
                            # Atualizações e componentes não são "programas"
                            if not nome or ler("SystemComponent") == 1 or ler("ParentKeyName"):
                                continue
                            if nome in vistos:
                                continue
                            vistos.add(nome)

                            data = str(ler("InstallDate", ""))
                            if len(data) == 8 and data.isdigit():
                                data = f"{data[6:8]}/{data[4:6]}/{data[0:4]}"

                            programas.append(Programa(
                                nome=nome,
                                versao=str(ler("DisplayVersion", "")),
                                editor=str(ler("Publisher", "")),
                                # EstimatedSize vem em KB
                                tamanho=int(ler("EstimatedSize", 0) or 0) * 1024,
                                instalado_em=data,
                                localizacao=str(ler("InstallLocation", "")),
                                comando_remocao=str(ler("QuietUninstallString")
                                                    or ler("UninstallString", "")),
                                identificador=nome_sub,
                                do_sistema=str(ler("Publisher", "")).startswith("Microsoft"),
                            ))
                    except OSError:
                        continue
        except OSError:
            continue
    return programas


# --- macOS -------------------------------------------------------------------

def _tamanhos_macos(pastas: list[Path]) -> dict[str, int]:
    """Um único `du` para todas as aplicações — muito mais rápido que um por app."""
    tamanhos: dict[str, int] = {}
    for pasta in pastas:
        if not pasta.is_dir():
            continue
        resultado = run(["du", "-sk", *[str(p) for p in pasta.glob("*.app")]], timeout=180)
        for linha in resultado.out.splitlines():
            partes = linha.split("\t", 1)
            if len(partes) == 2 and partes[0].strip().isdigit():
                tamanhos[partes[1].strip()] = int(partes[0]) * 1024
    return tamanhos


def _macos() -> list[Programa]:
    pastas = [Path("/Applications"), Path.home() / "Applications",
              Path("/Applications/Utilities")]
    tamanhos = _tamanhos_macos(pastas)
    programas: list[Programa] = []

    for pasta in pastas:
        if not pasta.is_dir():
            continue
        for app in sorted(pasta.glob("*.app")):
            versao, identificador, editor = "", "", ""
            try:
                with open(app / "Contents" / "Info.plist", "rb") as ficheiro:
                    info = plistlib.load(ficheiro)
                versao = str(info.get("CFBundleShortVersionString", ""))
                identificador = str(info.get("CFBundleIdentifier", ""))
                editor = identificador.split(".")[1] if identificador.count(".") >= 1 else ""
            except Exception:  # noqa: BLE001 - plists partidos existem
                pass

            try:
                usado = datetime.fromtimestamp(app.stat().st_atime).strftime("%d/%m/%Y")
                instalado = datetime.fromtimestamp(app.stat().st_birthtime).strftime("%d/%m/%Y")
            except (OSError, AttributeError):
                usado = instalado = ""

            programas.append(Programa(
                nome=app.stem,
                versao=versao,
                editor=editor,
                tamanho=tamanhos.get(str(app), 0),
                instalado_em=instalado,
                ultimo_uso=usado,
                localizacao=str(app),
                identificador=identificador,
                do_sistema=identificador.startswith("com.apple."),
            ))
    return programas


# --- Linux -------------------------------------------------------------------

def _linux() -> list[Programa]:
    programas: list[Programa] = []

    dpkg = run(["dpkg-query", "-W", "-f=${Package}\\t${Version}\\t${Installed-Size}\\t${Maintainer}\\n"],
               timeout=60)
    if dpkg.ok and dpkg.out:
        for linha in dpkg.out.splitlines():
            partes = linha.split("\t")
            if len(partes) < 3:
                continue
            nome, versao, tamanho = partes[0], partes[1], partes[2]
            editor = partes[3] if len(partes) > 3 else ""
            programas.append(Programa(
                nome=nome, versao=versao,
                editor=editor.split("<")[0].strip(),
                # Installed-Size do dpkg vem em KB
                tamanho=int(tamanho) * 1024 if tamanho.strip().isdigit() else 0,
                identificador=nome,
                do_sistema=nome.startswith(("lib", "linux-", "systemd", "python3-")),
            ))
        return programas

    rpm = run(["rpm", "-qa", "--queryformat", "%{NAME}\\t%{VERSION}\\t%{SIZE}\\t%{VENDOR}\\n"],
              timeout=60)
    if rpm.ok and rpm.out:
        for linha in rpm.out.splitlines():
            partes = linha.split("\t")
            if len(partes) < 3:
                continue
            programas.append(Programa(
                nome=partes[0], versao=partes[1],
                tamanho=int(partes[2]) if partes[2].isdigit() else 0,
                editor=partes[3] if len(partes) > 3 else "",
                identificador=partes[0],
                do_sistema=partes[0].startswith(("lib", "kernel", "systemd")),
            ))
    return programas


# --- API pública -------------------------------------------------------------

def listar(progress=None) -> list[Programa]:
    if progress:
        progress(10, "A ler a lista de programas instalados…")
    try:
        if IS_WINDOWS:
            programas = _windows()
        elif IS_MACOS:
            programas = _macos()
        elif IS_LINUX:
            programas = _linux()
        else:
            programas = []
    except Exception as exc:  # noqa: BLE001
        storage.log(f"PROGRAMAS erro a listar: {exc}")
        programas = []
    if progress:
        progress(100, f"{len(programas)} programas encontrados")
    return sorted(programas, key=lambda p: (-p.tamanho, p.nome.lower()))


def espaco_total(programas: list[Programa]) -> int:
    return sum(p.tamanho for p in programas)


def pode_remover(programa: Programa) -> tuple[bool, str]:
    if programa.do_sistema:
        return False, "Faz parte do sistema — removê-lo pode partir a máquina"
    if IS_WINDOWS and not programa.comando_remocao:
        return False, "Este programa não declara um desinstalador"
    return True, ""


def remover(programa: Programa) -> tuple[bool, str]:
    """Desinstala. No macOS vai para o Lixo, para haver forma de voltar atrás."""
    pode, motivo = pode_remover(programa)
    if not pode:
        return False, motivo

    if IS_WINDOWS:
        resultado = run(programa.comando_remocao, shell=True, timeout=900)
        ok, erro = resultado.ok, resultado.err
    elif IS_MACOS:
        caminho = programa.localizacao.replace('"', '\\"')
        # Pelo Finder, para o programa ir para o Lixo em vez de desaparecer
        resultado = run(
            ["osascript", "-e",
             f'tell application "Finder" to delete POSIX file "{caminho}"'],
            timeout=300,
        )
        ok, erro = resultado.ok, resultado.err
    elif IS_LINUX:
        resultado = run_elevated(
            f"sh -c 'command -v apt-get >/dev/null && apt-get -y remove {programa.identificador} "
            f"|| dnf -y remove {programa.identificador}'", timeout=900)
        ok, erro = resultado.ok, resultado.err
    else:
        return False, "Sistema não suportado"

    storage.log(f"PROGRAMAS remover '{programa.nome}' ({programa.tamanho_legivel}): "
                f"{'ok' if ok else erro}")
    return ok, erro or ""
