"""Coordenação de operações que alteram arquivos.

Apenas uma execução mutável pode ficar ativa por vez. Pré-visualizações são
somente leitura e não passam pelo coordenador. O estado é consultável
(``busy``/``owner``) e deve ser liberado pela página ao terminar, inclusive em
erro ou cancelamento.
"""
from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager

from .exceptions import ToolkitError


class OperationBusyError(ToolkitError):
    """Já existe uma operação mutável em andamento."""


class OperationCoordinator:
    """Permite uma única operação mutável ativa por vez."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._owner: str | None = None
        self._description = ""

    @property
    def busy(self) -> bool:
        with self._lock:
            return self._owner is not None

    @property
    def owner(self) -> str | None:
        with self._lock:
            return self._owner

    @property
    def description(self) -> str:
        with self._lock:
            return self._description

    def acquire(self, owner: str, description: str = "") -> None:
        """Reserva a operação para ``owner``; falha se já houver outra ativa."""
        with self._lock:
            if self._owner is not None:
                raise OperationBusyError(
                    f"Já existe uma operação em andamento: {self._description or self._owner}. "
                    "Aguarde a conclusão antes de iniciar outra execução."
                )
            self._owner = owner
            self._description = description or owner

    def release(self, owner: str) -> None:
        """Libera a operação se ``owner`` for o dono atual (caso contrário, ignora)."""
        with self._lock:
            if self._owner == owner:
                self._owner = None
                self._description = ""

    @contextmanager
    def operation(self, owner: str, description: str = "") -> Iterator[None]:
        """Reserva e libera automaticamente, inclusive quando há exceção."""
        self.acquire(owner, description)
        try:
            yield
        finally:
            self.release(owner)
