"""Pastas de dados, registo de operações e cópias de segurança para reverter."""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from pathlib import Path

from .platform_info import IS_WINDOWS

_LOCK = threading.Lock()


def data_dir() -> Path:
    if IS_WINDOWS:
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        path = base / "ReloadTechOptimizer"
    else:
        path = Path.home() / "Library" / "Application Support" / "ReloadTechOptimizer"
    path.mkdir(parents=True, exist_ok=True)
    return path


def reports_dir() -> Path:
    path = data_dir() / "relatorios"
    path.mkdir(parents=True, exist_ok=True)
    return path


def backups_dir() -> Path:
    path = data_dir() / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def log_path() -> Path:
    return data_dir() / "operacoes.log"


def log(message: str) -> None:
    """Regista tudo o que a ferramenta altera — auditável e legível."""
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{stamp}] {message}\n"
    with _LOCK:
        try:
            with open(log_path(), "a", encoding="utf-8") as handle:
                handle.write(line)
        except OSError:
            pass


def read_log(max_lines: int = 400) -> list[str]:
    try:
        with open(log_path(), encoding="utf-8", errors="replace") as handle:
            return handle.readlines()[-max_lines:]
    except OSError:
        return []


# --- Estado reversível -------------------------------------------------------

def _state_file() -> Path:
    return data_dir() / "estado.json"


def load_state() -> dict:
    try:
        with open(_state_file(), encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(state: dict) -> None:
    with _LOCK:
        try:
            tmp = _state_file().with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as handle:
                json.dump(state, handle, indent=2, ensure_ascii=False)
            tmp.replace(_state_file())
        except OSError:
            pass


def remember(section: str, key: str, value) -> None:
    """Guarda o valor original antes de o alterarmos, para permitir reverter."""
    state = load_state()
    state.setdefault(section, {})[key] = value
    save_state(state)


def recall(section: str, key: str, default=None):
    return load_state().get(section, {}).get(key, default)


def forget(section: str, key: str) -> None:
    state = load_state()
    if section in state and key in state[section]:
        del state[section][key]
        save_state(state)
