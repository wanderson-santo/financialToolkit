import sqlite3
import unittest
from datetime import date, datetime

from core.base_module import Result
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


class HistoryTests(TempDirCase):
    def test_historico_config_favoritos(self):
        h = HistoryService(self.tmp / "t.db")

        class M:
            module_id, name, version = "m1", "Módulo 1", "1.0"

        exec_id = h.start(M, "execute", {"a": 1})
        h.finish(exec_id, Result(status="success", summary="ok", processed=3, warnings=1),
                 [("2026-01-01 10:00:00", "info", "olá")])
        self.assertEqual(h.get(exec_id)["status"], "success")
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
        self.assertEqual(h2.recent(1)[0]["status"], "interrupted")

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
