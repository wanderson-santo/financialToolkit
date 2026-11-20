import csv
import os
import unittest
from pathlib import Path
from unittest import mock

from core.base_module import Result, SUCCESS
from core.export_service import export_rows
from core.history_service import (
    DETAILS_INLINE_LIMIT, DETAILS_MAX_ROWS, HistoryService,
)
from core.paths import details_dir
from tests.helpers import TempDirCase


class Module:
    module_id, name, version = "m1", "Módulo 1", "1.0"


class HistoryDetailsTests(TempDirCase):
    def setUp(self):
        super().setUp()
        self.details_root = self.tmp / "details"
        self.history = HistoryService(self.tmp / "historico.db", details_root=self.details_root)

    def finish(self, details, history=None):
        history = history or self.history
        exec_id = history.start(Module, "execute", {})
        history.finish(exec_id, Result(status=SUCCESS, summary="ok", details=details), [])
        return exec_id

    def test_zero_detalhes(self):
        exec_id = self.finish([])

        row = self.history.get(exec_id)
        self.assertEqual(row["details_count"], 0)
        self.assertIsNone(row["details_file"])
        self.assertEqual(self.history.details(exec_id), [])
        self.assertEqual(self.history.all_details(exec_id), [])

    def test_poucos_detalhes_ficam_no_banco(self):
        details = [
            {"nome": "João d'Ávila", "obs": 'aspas "x"\nsegunda linha', "valor": 1234.56},
            {"nome": "", "obs": None, "valor": 0},
        ]
        exec_id = self.finish(details)

        row = self.history.get(exec_id)
        self.assertIsNone(row["details_file"])
        self.assertEqual(row["details_count"], 2)
        self.assertEqual(self.history.details(exec_id), details)
        self.assertEqual(self.history.all_details(exec_id), details)
        self.assertFalse(self.details_root.exists())

    def test_muitos_detalhes_vao_para_arquivo_externo(self):
        details = [{"linha": n, "texto": f"registro {n}", "acento": "ção"} for n in range(1200)]
        exec_id = self.finish(details)

        row = self.history.get(exec_id)
        self.assertEqual(row["details_count"], 1200)
        self.assertEqual(row["details_file"], f"details-{exec_id}.jsonl")
        path = self.details_root / row["details_file"]
        self.assertTrue(path.exists())
        self.assertEqual(len(path.read_text(encoding="utf-8").splitlines()), 1200)

        self.assertEqual(self.history.details(exec_id, limit=200), details[:200])
        self.assertEqual(self.history.details(exec_id, limit=2, offset=5), details[5:7])
        self.assertEqual(self.history.details(exec_id), details)
        self.assertEqual(self.history.all_details(exec_id), details)

        with self.history._conn() as conn:
            inline = conn.execute(
                "SELECT COUNT(*) FROM execution_details WHERE execution_id=?", (exec_id,)
            ).fetchone()[0]
        self.assertEqual(inline, 0)

    def test_detalhes_externos_sobrevivem_ao_reinicio(self):
        details = [{"n": n} for n in range(DETAILS_INLINE_LIMIT + 10)]
        exec_id = self.finish(details)

        reopened = HistoryService(self.tmp / "historico.db", details_root=self.details_root)
        self.assertEqual(reopened.all_details(exec_id), details)

    def test_falha_no_arquivo_externo_recorre_ao_banco(self):
        details = [{"n": n} for n in range(DETAILS_INLINE_LIMIT + 1)]
        with mock.patch.object(HistoryService, "_write_details_file", side_effect=OSError("sem permissão")):
            with self.assertLogs("finance_toolkit", level="ERROR"):
                exec_id = self.finish(details)

        row = self.history.get(exec_id)
        self.assertIsNone(row["details_file"])
        self.assertEqual(row["details_count"], len(details))
        self.assertEqual(self.history.all_details(exec_id), details)
        self.assertEqual(list(self.details_root.glob("*.tmp")), [])

    def test_arquivo_externo_ausente_nao_quebra_consulta(self):
        details = [{"n": n} for n in range(DETAILS_INLINE_LIMIT + 1)]
        exec_id = self.finish(details)
        (self.details_root / self.history.get(exec_id)["details_file"]).unlink()

        with self.assertLogs("finance_toolkit", level="ERROR"):
            self.assertEqual(self.history.details(exec_id), [])

    def test_arquivo_externo_ilegivel_nao_quebra_consulta(self):
        details = [{"n": n} for n in range(DETAILS_INLINE_LIMIT + 1)]
        exec_id = self.finish(details)
        path = self.details_root / self.history.get(exec_id)["details_file"]
        path.write_bytes(b"\xff\xfe")

        with self.assertLogs("finance_toolkit", level="ERROR"):
            self.assertEqual(self.history.details(exec_id), [])

    def test_linha_corrompida_no_arquivo_e_ignorada(self):
        details = [{"n": n} for n in range(DETAILS_INLINE_LIMIT + 1)]
        exec_id = self.finish(details)
        path = self.details_root / self.history.get(exec_id)["details_file"]
        with path.open("a", encoding="utf-8") as fh:
            fh.write("{invalido\n")

        with self.assertLogs("finance_toolkit", level="WARNING"):
            self.assertEqual(self.history.all_details(exec_id), details)

    def test_limite_de_linhas_por_execucao(self):
        details = [{"n": n} for n in range(10)]
        with mock.patch("core.history_service.DETAILS_MAX_ROWS", 5), \
                mock.patch("core.history_service.DETAILS_INLINE_LIMIT", 2), \
                self.assertLogs("finance_toolkit", level="WARNING") as logs:
            exec_id = self.finish(details)

        row = self.history.get(exec_id)
        self.assertEqual(row["details_count"], 5)
        self.assertEqual(self.history.all_details(exec_id), details[:5])
        self.assertIn("truncados", "\n".join(logs.output))
        self.assertIn("truncados", self.history.events(exec_id)[-1]["message"])

    def test_constantes_documentadas(self):
        self.assertEqual(DETAILS_INLINE_LIMIT, 1000)
        self.assertEqual(DETAILS_MAX_ROWS, 50_000)

    def test_pasta_padrao_de_detalhes(self):
        expected = Path(os.environ["FINANCE_TOOLKIT_HOME"]) / "details"
        self.assertEqual(details_dir(), expected)
        self.assertTrue(expected.is_dir())

    def test_exportacao_dos_detalhes(self):
        details = [
            {"nome": "João", "valor": 10},
            {"nome": "=1+1", "valor": 20},
        ]
        exec_id = self.finish(details)
        path = self.tmp / "detalhes.csv"

        export_rows(self.history.all_details(exec_id), path)

        with path.open(encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.reader(fh, delimiter=";"))
        self.assertEqual(rows[0], ["nome", "valor"])
        self.assertEqual(rows[1], ["João", "10"])
        self.assertEqual(rows[2], ["'=1+1", "20"])
