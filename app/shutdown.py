"""Encerramento seguro de operações em andamento, independente da interface."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Iterable, Protocol

DEFAULT_SHUTDOWN_TIMEOUT = 10.0


class StoppableOperation(Protocol):
    @property
    def is_running(self) -> bool:
        ...

    def request_cancel(self) -> None:
        ...

    def interrupt(self, reason: str) -> None:
        ...


@dataclass(frozen=True)
class ShutdownResult:
    confirmed: bool
    timed_out: bool
    active: int


def shutdown_operations(
    operations: Iterable[StoppableOperation],
    *,
    confirm: Callable[[int], bool],
    warn: Callable[[int], None],
    pump: Callable[[], None],
    timeout: float = DEFAULT_SHUTDOWN_TIMEOUT,
    poll_interval: float = 0.05,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> ShutdownResult:
    """Confirma, cancela e aguarda operações antes de fechar a aplicação.

    ``pump`` processa eventos da interface (ou avança um cenário de teste)
    enquanto a espera acontece. Operações que não terminarem até ``timeout``
    são marcadas como interrompidas e o usuário é avisado por ``warn``.
    """
    active = [op for op in operations if op.is_running]
    if not active:
        return ShutdownResult(confirmed=True, timed_out=False, active=0)
    if not confirm(len(active)):
        return ShutdownResult(confirmed=False, timed_out=False, active=len(active))

    for op in active:
        op.request_cancel()

    deadline = clock() + max(0.0, timeout)
    while any(op.is_running for op in active):
        if clock() >= deadline:
            break
        pump()
        if not any(op.is_running for op in active):
            break
        sleep(min(poll_interval, max(0.0, deadline - clock())))

    remaining = [op for op in active if op.is_running]
    for op in remaining:
        op.interrupt("Aplicativo encerrado antes de a operação terminar.")
    if remaining:
        warn(len(remaining))
    return ShutdownResult(confirmed=True, timed_out=bool(remaining), active=len(remaining))
