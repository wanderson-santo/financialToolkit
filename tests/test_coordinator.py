import threading
import unittest

from core.exceptions import CancelledError
from core.operation_coordinator import OperationBusyError, OperationCoordinator


class CoordinatorTests(unittest.TestCase):
    def test_aquisicao_e_liberacao(self):
        coordinator = OperationCoordinator()
        self.assertFalse(coordinator.busy)
        coordinator.acquire("organizer", "Organizador de pastas")
        self.assertTrue(coordinator.busy)
        self.assertEqual(coordinator.owner, "organizer")
        self.assertEqual(coordinator.description, "Organizador de pastas")
        coordinator.release("organizer")
        self.assertFalse(coordinator.busy)
        self.assertIsNone(coordinator.owner)

    def test_segunda_aquisicao_e_bloqueada(self):
        coordinator = OperationCoordinator()
        coordinator.acquire("organizer", "Organizador de pastas")
        with self.assertRaises(OperationBusyError) as ctx:
            coordinator.acquire("duplicates", "Detector de duplicados")
        self.assertIn("Organizador de pastas", str(ctx.exception))
        self.assertIn("Aguarde", str(ctx.exception))
        self.assertEqual(coordinator.owner, "organizer")

    def test_dono_diferente_nao_libera(self):
        coordinator = OperationCoordinator()
        coordinator.acquire("organizer", "Organizador de pastas")
        coordinator.release("duplicates")
        self.assertTrue(coordinator.busy)
        self.assertEqual(coordinator.owner, "organizer")

    def test_liberacao_em_excecao(self):
        coordinator = OperationCoordinator()
        with self.assertRaises(ValueError):
            with coordinator.operation("organizer", "Organizador de pastas"):
                self.assertTrue(coordinator.busy)
                raise ValueError("falha simulada")
        self.assertFalse(coordinator.busy)

    def test_liberacao_em_cancelamento(self):
        coordinator = OperationCoordinator()
        with self.assertRaises(CancelledError):
            with coordinator.operation("organizer", "Organizador de pastas"):
                raise CancelledError("Execução cancelada pelo usuário.")
        self.assertFalse(coordinator.busy)

    def test_duas_aquisicoes_concorrentes(self):
        coordinator = OperationCoordinator()
        barrier = threading.Barrier(3)
        results: list[tuple[str, str]] = []

        def run(owner: str) -> None:
            barrier.wait()
            try:
                coordinator.acquire(owner, owner)
            except OperationBusyError:
                results.append(("bloqueada", owner))
            else:
                results.append(("ativa", owner))

        threads = [threading.Thread(target=run, args=(owner,)) for owner in ("a", "b")]
        for thread in threads:
            thread.start()
        barrier.wait()
        for thread in threads:
            thread.join()

        self.assertEqual(sorted(status for status, _ in results), ["ativa", "bloqueada"])
        self.assertTrue(coordinator.busy)
        coordinator.release(coordinator.owner)
        self.assertFalse(coordinator.busy)


if __name__ == "__main__":
    unittest.main()
