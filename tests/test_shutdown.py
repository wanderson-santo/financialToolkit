import unittest

from app.shutdown import ShutdownResult, shutdown_operations


class FakeOperation:
    def __init__(self, running: bool = True, finish_on_pump: bool = False):
        self.running = running
        self.finish_on_pump = finish_on_pump
        self.cancelled = False
        self.interrupted = None

    @property
    def is_running(self) -> bool:
        return self.running

    def request_cancel(self) -> None:
        self.cancelled = True

    def interrupt(self, reason: str) -> None:
        self.interrupted = reason
        self.running = False


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += max(0.0, seconds)


class ShutdownTests(unittest.TestCase):
    def test_sem_operacoes_fecha_direto(self):
        calls = []
        result = shutdown_operations(
            [], confirm=lambda n: calls.append(n) or True,
            warn=lambda n: calls.append(("warn", n)), pump=lambda: None,
        )
        self.assertEqual(result, ShutdownResult(confirmed=True, timed_out=False, active=0))
        self.assertEqual(calls, [])

    def test_confirmacao_negada_nao_cancela(self):
        op = FakeOperation()
        result = shutdown_operations(
            [op], confirm=lambda n: False, warn=lambda n: None, pump=lambda: None, timeout=1.0,
        )
        self.assertFalse(result.confirmed)
        self.assertFalse(op.cancelled)
        self.assertIsNone(op.interrupted)

    def test_cancelamento_conclui_antes_do_timeout(self):
        op = FakeOperation(finish_on_pump=True)
        clock = FakeClock()

        def pump():
            op.running = False

        result = shutdown_operations(
            [op], confirm=lambda n: True, warn=lambda n: None, pump=pump,
            timeout=1.0, clock=clock, sleep=clock.sleep,
        )
        self.assertTrue(op.cancelled)
        self.assertTrue(result.confirmed)
        self.assertFalse(result.timed_out)
        self.assertIsNone(op.interrupted)

    def test_timeout_interrompe_e_avisa(self):
        op = FakeOperation()
        clock = FakeClock()
        warnings = []
        result = shutdown_operations(
            [op], confirm=lambda n: True, warn=warnings.append, pump=lambda: None,
            timeout=0.2, poll_interval=0.05, clock=clock, sleep=clock.sleep,
        )
        self.assertTrue(result.timed_out)
        self.assertEqual(result.active, 1)
        self.assertIsNotNone(op.interrupted)
        self.assertEqual(warnings, [1])

    def test_multiplas_operacoes_so_interrompe_pendentes(self):
        concluida = FakeOperation(finish_on_pump=True)
        pendente = FakeOperation()
        clock = FakeClock()
        warnings = []

        def pump():
            concluida.running = False

        result = shutdown_operations(
            [concluida, pendente], confirm=lambda n: n == 2, warn=warnings.append, pump=pump,
            timeout=0.1, poll_interval=0.05, clock=clock, sleep=clock.sleep,
        )
        self.assertTrue(concluida.cancelled)
        self.assertTrue(pendente.cancelled)
        self.assertIsNone(concluida.interrupted)
        self.assertIsNotNone(pendente.interrupted)
        self.assertTrue(result.timed_out)
        self.assertEqual(warnings, [1])
