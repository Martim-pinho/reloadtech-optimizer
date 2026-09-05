"""Empacota a aplicação gráfica num executável (.exe no Windows, .app no macOS).

    pip install pyinstaller
    python packaging/build-desktop.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def main() -> int:
    if not (RAIZ / "reloadtech").is_dir():
        print("Corre este script a partir da raiz do repositório.", file=sys.stderr)
        return 1

    comando = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--windowed",
        "--name", "ReloadTech Optimizer",
        "--distpath", str(RAIZ / "dist"),
        "--workpath", str(RAIZ / "build" / "pyinstaller"),
        "--specpath", str(RAIZ / "build"),
        # psutil e reportlab trazem módulos que o analisador não apanha sozinho
        "--hidden-import", "psutil",
        "--hidden-import", "reportlab.graphics.barcode",
        str(RAIZ / "reloadtech" / "__main__.py"),
    ]
    if sys.platform.startswith("win"):
        # Sem isto, as otimizações de serviços falham por falta de privilégios.
        comando.insert(-1, "--uac-admin")

    print("A empacotar…\n  " + " ".join(comando))
    return subprocess.call(comando)


if __name__ == "__main__":
    sys.exit(main())
