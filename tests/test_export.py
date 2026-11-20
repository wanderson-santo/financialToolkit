import csv

import pandas as pd
from openpyxl import load_workbook

from core.export_service import export_rows, export_sheets
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

    def test_abas_truncadas_nao_se_sobrescrevem(self):
        base = "A" * 31
        path = self.tmp / "abas.xlsx"
        export_sheets(
            {base + "1": pd.DataFrame({"v": [1]}), base + "2": pd.DataFrame({"v": [2]})},
            path,
        )
        wb = load_workbook(path)
        self.assertEqual(wb.sheetnames, [base, "A" * 29 + "_2"])
        self.assertEqual(wb[base]["A2"].value, 1)
        self.assertEqual(wb["A" * 29 + "_2"]["A2"].value, 2)

    def test_abas_com_mesmo_nome_ignorando_maiusculas(self):
        path = self.tmp / "abas.xlsx"
        export_sheets(
            {"Dados": pd.DataFrame({"v": [1]}), "dados": pd.DataFrame({"v": [2]})},
            path,
        )
        wb = load_workbook(path)
        self.assertEqual(wb.sheetnames, ["Dados", "dados_2"])
        self.assertEqual(wb["Dados"]["A2"].value, 1)
        self.assertEqual(wb["dados_2"]["A2"].value, 2)

    def test_nome_vazio_e_caracteres_invalidos(self):
        path = self.tmp / "abas.xlsx"
        export_sheets(
            {
                "": pd.DataFrame({"v": [1]}),
                "a/b:c*?[]\\": pd.DataFrame({"v": [2]}),
                "Planilha": pd.DataFrame({"v": [3]}),
            },
            path,
        )
        wb = load_workbook(path)
        self.assertEqual(len(wb.sheetnames), 3)
        self.assertEqual(wb.sheetnames[0], "Planilha")
        self.assertEqual(wb.sheetnames[2], "Planilha_2")
        for name in wb.sheetnames:
            with self.subTest(name=name):
                self.assertLessEqual(len(name), 31)
                self.assertFalse(any(ch in name for ch in "[]:*?/\\"))
        self.assertEqual([wb[name]["A2"].value for name in wb.sheetnames], [1, 2, 3])
