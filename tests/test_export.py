import csv

from openpyxl import load_workbook

from core.export_service import export_rows
from tests.helpers import TempDirCase


class ExportSecurityTests(TempDirCase):
    PAYLOADS = [
        "=1+1", "+1+1", "-1+1", "@SUM(A1)",
        "\t=cmd", "\r=cmd", "\n=cmd", "  =cmd",
        "\ufeff=cmd", "\u200b=cmd",
    ]

    def test_csv_neutraliza_formulas(self):
        path = self.tmp / "saida.csv"
        export_rows([{"payload": p} for p in self.PAYLOADS], path)
        with path.open(encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.reader(fh, delimiter=";"))
        self.assertEqual(rows[0], ["payload"])
        values = [row[0] for row in rows[1:]]
        self.assertEqual(len(values), len(self.PAYLOADS))
        for raw, value in zip(self.PAYLOADS, values):
            with self.subTest(payload=raw):
                self.assertTrue(value.startswith("'"), value)

    def test_csv_preserva_numeros(self):
        path = self.tmp / "numeros.csv"
        export_rows([{"valor": -123.45, "texto": "-123,45", "positivo": "+123"}], path)
        with path.open(encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.reader(fh, delimiter=";"))
        self.assertEqual(rows[1], ["-123.45", "-123,45", "+123"])

    def test_xlsx_neutraliza_formulas(self):
        path = self.tmp / "saida.xlsx"
        export_rows([{"payload": p} for p in self.PAYLOADS], path)
        ws = load_workbook(path).active
        rows = ws.iter_rows(min_row=2, max_col=1)
        for row, raw in zip(rows, self.PAYLOADS):
            cell = row[0]
            with self.subTest(payload=raw):
                self.assertEqual(cell.data_type, "s")
                self.assertTrue(cell.value.startswith("'"), cell.value)

    def test_xlsx_preserva_numeros(self):
        path = self.tmp / "numeros.xlsx"
        export_rows([{"valor": -123.45, "texto": "-123,45"}], path)
        ws = load_workbook(path).active
        self.assertEqual(ws["A2"].value, -123.45)
        self.assertEqual(ws["A2"].data_type, "n")
        self.assertEqual(ws["B2"].value, "-123,45")
        self.assertFalse(str(ws["B2"].value).startswith("'"))

    def test_cabecalhos_tambem_sao_protegidos(self):
        path = self.tmp / "cabecalho.xlsx"
        export_rows([{"=cmd": "x", "@cmd": "y", "seguro": "z"}], path)
        ws = load_workbook(path).active
        self.assertEqual([c.value for c in ws[1]], ["'=cmd", "'@cmd", "seguro"])
