import sqlite3
import unittest
from datetime import date, datetime

from core.base_module import (
    CANCELLED, FAILED, INTERRUPTED, PARTIAL, RUNNING, STATUS_LABELS, SUCCESS,
    Result, build_result, validate_status,
)
from core.execution_context import ExecutionContext
from core.history_service import HistoryService
from core.normalizers import (
    as_text, clean_text, cnpj_is_valid, format_cnpj, is_blank, normalize_cnpj, parse_date, parse_number,
)
from core.validation_service import find_duplicates, validate_cnpj
from tests.helpers import TempDirCase


class NormalizerTests(unittest.TestCase):
    def test_cnpj(self):
        self.assertTrue(cnpj_is_valid("11222333000181"))
        self.assertTrue(cnpj_is_valid("00000000000191"))
        self.assertFalse(cnpj_is_valid("11222333000182"))
        self.assertFalse(cnpj_is_valid("11111111111111"))
        self.assertEqual(normalize_cnpj("11.222.333/0001-81"), "11222333000181")
        self.assertEqual(normalize_cnpj(12345678000190.0), "12345678000190")
        self.assertEqual(normalize_cnpj("191"), "00000000000191")  # zeros perdidos no Excel
        self.assertIsNone(normalize_cnpj("123456789012345"))
        self.assertIsNone(normalize_cnpj(""))
        self.assertEqual(format_cnpj("11222333000181"), "11.222.333/0001-81")

    def test_cnpj_alfanumerico(self):
        base = "12ABC34501DE"
        w = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]

        def dv(b, ws):
            r = sum((ord(c) - 48) * x for c, x in zip(b, ws)) % 11
            return "0" if r < 2 else str(11 - r)

        d1 = dv(base, w)
        d2 = dv(base + d1, [6] + w)
        self.assertTrue(cnpj_is_valid(base + d1 + d2))
        self.assertFalse(cnpj_is_valid(base + d1 + str((int(d2) + 1) % 10)))

    def test_numeros(self):
        self.assertEqual(parse_number("R$ 1.234,56"), 1234.56)
        self.assertEqual(parse_number("(1.234,56)"), -1234.56)
        self.assertEqual(parse_number("1.234,56-"), -1234.56)
        self.assertEqual(parse_number("1,234.56", "intl"), 1234.56)
        self.assertEqual(parse_number(10), 10.0)
        self.assertIsNone(parse_number("abc"))
        self.assertIsNone(parse_number(""))
        self.assertIsNone(parse_number(True))

    def test_datas(self):
        self.assertEqual(parse_date("31/01/2024"), date(2024, 1, 31))
        self.assertEqual(parse_date("2024-01-31 00:00:00"), date(2024, 1, 31))
        self.assertEqual(parse_date(datetime(2024, 1, 31, 10, 0)), date(2024, 1, 31))
        self.assertEqual(parse_date(45000), date(2023, 3, 15))
        self.assertIsNone(parse_date("31/02/2024"))
        self.assertIsNone(parse_date("texto"))

    def test_texto(self):
        self.assertEqual(clean_text("  a\u00a0 b\u200bc \n d "), "a bc d")
        self.assertTrue(is_blank("  ") and is_blank(None) and is_blank(float("nan")))
        self.assertEqual(as_text(5.0), "5")
        self.assertEqual(as_text(5.5), "5.5")

    def test_validation_service(self):
        self.assertEqual(validate_cnpj("11.222.333/0001-81")[:2], (True, "Válido"))
        self.assertEqual(validate_cnpj("")[1], "Vazio")
        self.assertEqual(validate_cnpj("11222333000182")[1], "Dígitos verificadores inválidos")
        self.assertEqual(find_duplicates(["a", "b", "a", ""]), {"a": [0, 2]})


class StatusTests(unittest.TestCase):
    def test_build_result_calcula_pelos_contadores(self):
        self.assertEqual(build_result("ok", processed=0).status, SUCCESS)
        self.assertEqual(build_result("ok", processed=0, warnings=2).status, SUCCESS)
        self.assertEqual(build_result("falhou", processed=0, errors=1).status, FAILED)
        self.assertEqual(build_result("parcial", processed=2, errors=1).status, PARTIAL)

    def test_build_result_status_explicito_tem_prioridade(self):
        result = build_result("cancelado", processed=2, errors=3, status=CANCELLED)
        self.assertEqual(result.status, CANCELLED)
        self.assertEqual((result.processed, result.errors), (2, 3))

    def test_status_desconhecido_e_rejeitado(self):
        for invalid in ("", "sucesso", "finished", RUNNING):
            with self.subTest(status=invalid):
                with self.assertRaises(ValueError):
                    build_result("x", processed=0, status=invalid)
                with self.assertRaises(ValueError):
                    Result(status=invalid)
        with self.assertRaises(ValueError):
            validate_status("bogus")

    def test_todos_os_status_tem_rotulo(self):
        self.assertEqual(set(STATUS_LABELS), {SUCCESS, PARTIAL, FAILED, CANCELLED, RUNNING, INTERRUPTED})
        for status, label in STATUS_LABELS.items():
            with self.subTest(status=status):
                self.assertTrue(label)
        for status in (SUCCESS, PARTIAL, FAILED, CANCELLED, INTERRUPTED):
            self.assertEqual(validate_status(status), status)
        # "running" é estado do histórico, não status de resultado.
        self.assertNotIn(RUNNING, {SUCCESS, PARTIAL, FAILED, CANCELLED, INTERRUPTED})


class ExecutionContextTests(unittest.TestCase):
    def test_reutiliza_run_id_informado(self):
        ctx = ExecutionContext("m1", run_id="run123")
        self.assertEqual(ctx.run_id, "run123")
        with self.assertLogs("finance_toolkit", level="INFO") as logs:
            ctx.log("mensagem")
        self.assertIn("[m1 run123] mensagem", logs.output[0])

    def test_gera_run_id_quando_ausente(self):
        first = ExecutionContext("m1").run_id
        second = ExecutionContext("m1").run_id
        self.assertEqual(len(first), 10)
        self.assertNotEqual(first, second)


class HistoryTests(TempDirCase):
    def test_historico_config_favoritos(self):
        h = HistoryService(self.tmp / "t.db")

        class M:
            module_id, name, version = "m1", "Módulo 1", "1.0"

        exec_id = h.start(M, "execute", {"a": 1})
        h.finish(exec_id, Result(status=SUCCESS, summary="ok", processed=3, warnings=1),
                 [("2026-01-01 10:00:00", "info", "olá")])
        self.assertEqual(h.get(exec_id)["status"], SUCCESS)
        self.assertEqual(h.events(exec_id)[0]["message"], "olá")
        self.assertEqual(h.stats()["alerts"], 1)
        h.start(M, "preview", {})
        self.assertEqual(h.stats()["total"], 1)  # preview não conta

        h.set_settings("m1", {"x": "y"})
        self.assertEqual(h.get_settings("m1"), {"x": "y"})
        self.assertTrue(h.toggle_favorite("m1"))
        self.assertTrue(h.is_favorite("m1"))
        self.assertFalse(h.toggle_favorite("m1"))

        h2 = HistoryService(self.tmp / "t.db")  # reabrir marca "running" como interrompido
        self.assertEqual(h2.recent(1)[0]["status"], INTERRUPTED)

    def test_start_grava_run_id(self):
        h = HistoryService(self.tmp / "t.db")

        class M:
            module_id, name, version = "m1", "Módulo 1", "1.0"

        exec_id = h.start(M, "execute", {}, run_id="run123")
        self.assertEqual(h.get(exec_id)["run_id"], "run123")
        self.assertEqual(h.recent(1)[0]["run_id"], "run123")

    def test_finish_registra_cancelamento_e_interrupcao(self):
        h = HistoryService(self.tmp / "t.db")

        class M:
            module_id, name, version = "m1", "Módulo 1", "1.0"

        cancel_id = h.start(M, "execute", {})
        h.finish(cancel_id, Result(status=CANCELLED, summary="Cancelado pelo usuário."), [])
        interrupted_id = h.start(M, "preview", {})
        h.finish(
            interrupted_id,
            Result(status=INTERRUPTED, summary="Aplicativo encerrado.", is_preview=True),
            [("2026-01-01 10:00:00", "info", "interrompido")],
        )

        canc = h.get(cancel_id)
        self.assertEqual(canc["status"], CANCELLED)
        self.assertEqual(canc["summary"], "Cancelado pelo usuário.")
        self.assertIsNotNone(canc["finished_at"])

        inter = h.get(interrupted_id)
        self.assertEqual(inter["status"], INTERRUPTED)
        self.assertIsNotNone(inter["finished_at"])
        self.assertEqual(h.events(interrupted_id)[0]["message"], "interrompido")

    def test_stats_reconhece_todos_os_status(self):
        h = HistoryService(self.tmp / "t.db")

        class M:
            module_id, name, version = "m1", "Módulo 1", "1.0"

        def finish(status, warnings=0):
            exec_id = h.start(M, "execute", {})
            h.finish(exec_id, build_result("x", processed=1, warnings=warnings, status=status), [])

        finish(SUCCESS)
        finish(SUCCESS, warnings=1)
        finish(PARTIAL)
        finish(FAILED)
        finish(CANCELLED)
        finish(INTERRUPTED)

        self.assertEqual(
            h.stats(),
            {"total": 6, "ok": 1, "alerts": 2, "failed": 1, "cancelled": 1},
        )

    def test_recupera_banco_corrompido(self):
        db = self.tmp / "corrompido.db"
        original = b"isto nao e um banco sqlite"
        db.write_bytes(original)
        recovered = []

        with self.assertLogs("finance_toolkit", level="ERROR") as logs:
            h = HistoryService.open_with_recovery(
                db, on_recover=lambda backup, exc: recovered.append((backup, exc)),
            )

        backups = list(self.tmp.glob("corrompido.db.corrupt-*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), original)
        self.assertTrue(db.exists())
        self.assertEqual(recovered[0][0], backups[0])
        self.assertIsInstance(recovered[0][1], sqlite3.DatabaseError)
        self.assertIn("corrompido", logs.output[0].lower())

        h.set_settings("m1", {"ok": True})
        self.assertEqual(h.get_settings("m1"), {"ok": True})

    def test_erro_de_pasta_nao_e_tratado_como_corrupcao(self):
        db = self.tmp / "pasta_inexistente" / "t.db"
        with self.assertRaises(sqlite3.DatabaseError):
            HistoryService.open_with_recovery(db)
        self.assertEqual(list(self.tmp.glob("**/*.corrupt-*")), [])


if __name__ == "__main__":
    unittest.main()
