"""Execução de tarefas fora do fio principal, para a janela nunca bloquear."""
from __future__ import annotations

from PySide6.QtCore import QThread, Signal


class Tarefa(QThread):
    """Corre `funcao` numa thread própria e comunica progresso e resultado.

    Se a função aceitar um parâmetro `progress`, recebe um callback que emite
    o sinal `progresso`.
    """

    progresso = Signal(int, str)
    terminado = Signal(object)
    falhou = Signal(str)

    def __init__(self, funcao, *args, com_progresso: bool = True, **kwargs) -> None:
        super().__init__()
        self._funcao = funcao
        self._args = args
        self._kwargs = kwargs
        self._com_progresso = com_progresso

    def run(self) -> None:  # noqa: D102
        try:
            if self._com_progresso:
                self._kwargs["progress"] = lambda pct, texto: self.progresso.emit(int(pct), str(texto))
            resultado = self._funcao(*self._args, **self._kwargs)
            self.terminado.emit(resultado)
        except Exception as exc:  # noqa: BLE001 - erros vão para a interface
            self.falhou.emit(str(exc))
