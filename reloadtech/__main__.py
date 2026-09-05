"""Permite correr a ferramenta com `python -m reloadtech`."""
import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
