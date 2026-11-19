"""Contexto entregue a cada execução: log, progresso e cancelamento seguro."""
from __future__ import annotations

import logging
import threading
import time
import uuid

from .exceptions import CancelledError
from .logging_service import get_logger

_LEVELS = {"info": logging.INFO, "warning": logging.WARNING, "error": logging.ERROR}


class ExecutionContext:
    """O `emit(kind, *payload)` recebe ("log", nivel, msg) e ("progress", atual, total, etapa).

    Ele costuma ser uma fila: a thread de trabalho nunca toca na interface.
    """

    def __init__(self, module_id: str, emit=None, cancel_event: threading.Event | None = None):
        self.module_id = module_id
        self.run_id = uuid.uuid4().hex[:10]
        self._emit = emit or (lambda *args: None)
        self._cancel = cancel_event or threading.Event()
        self._last_progress = 0.0
        self._logger = get_logger()

    def log(self, message: str, level: str = "info") -> None:
        self._logger.log(_LEVELS.get(level, logging.INFO), "[%s %s] %s", self.module_id, self.run_id, message)
        self._emit("log", level, message)

    def progress(self, current: int, total: int, step: str = "") -> None:
        now = time.monotonic()
        if current >= total or now - self._last_progress >= 0.05:
            self._last_progress = now
            self._emit("progress", current, total, step)

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def check_cancel(self) -> None:
        if self._cancel.is_set():
            raise CancelledError("Execução cancelada pelo usuário.")
