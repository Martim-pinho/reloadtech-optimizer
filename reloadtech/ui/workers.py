"""Execução de tarefas fora do fio principal, para a janela nunca bloquear."""
from __future__ import annotations

from PySide6.QtCore import QThread, Signal

# Registo das tarefas vivas. Sem isto, fechar a janela enquanto uma análise
# corre destrói a QThread a meio — o Qt avisa e a aplicação pode ir abaixo ao
# sair, mesmo depois de o utilizador achar que já fechou tudo.
_EM_CURSO: set["Tarefa"] = set()


def esperar_todas(limite_ms: int = 3000) -> None:
    """Espera que as tarefas em curso terminem. Chamada ao fechar a janela."""
    for tarefa in list(_EM_CURSO):
        if tarefa.isRunning():
            tarefa.requestInterruption()
            tarefa.wait(limite_ms)


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

    def start(self, *args, **kwargs) -> None:  # noqa: D102
        _EM_CURSO.add(self)
        self.finished.connect(lambda: _EM_CURSO.discard(self))
        super().start(*args, **kwargs)

    def run(self) -> None:  # noqa: D102
        try:
            if self._com_progresso:
                self._kwargs["progress"] = lambda pct, texto: self.progresso.emit(int(pct), str(texto))
            resultado = self._funcao(*self._args, **self._kwargs)
            self.terminado.emit(resultado)
        except Exception as exc:  # noqa: BLE001 - erros vão para a interface
            self.falhou.emit(str(exc))
