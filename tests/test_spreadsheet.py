import pandas as pd

from core.spreadsheet_service import read_table, unique_headers
from tests.helpers import TempDirCase


class HeaderDedupTests(TempDirCase):
    def test_unique_headers_deterministico(self):
        self.assertEqual(
            unique_headers(["X", " X ", "", "X", "X_2"]),
            ["X", "X_2", "Coluna", "X_3", "X_2_2"],
        )
        self.assertEqual(
            unique_headers(["Unnamed: 0", None, "   "]),
            ["Coluna", "Coluna_2", "Coluna_3"],
        )

    def test_csv_deduplica_e_preserva_todas_as_colunas(self):
        path = self.write("dup.csv", "X; X ;;Y\n1;2;3;4\n")
        with self.assertLogs("finance_toolkit", level="WARNING") as logs:
            df = read_table(path)

        self.assertEqual(list(df.columns), ["X", "X_2", "Coluna", "Y"])
        self.assertEqual(df.iloc[0].tolist(), ["1", "2", "3", "4"])
        self.assertIn("Cabeçalhos ajustados", "\n".join(logs.output))

    def test_xlsx_deduplica_e_preserva_todas_as_colunas(self):
        path = self.tmp / "dup.xlsx"
        pd.DataFrame([[1, 2, 3, 4]], columns=["X", " X ", "", "Y"]).to_excel(path, index=False)
        with self.assertLogs("finance_toolkit", level="WARNING") as logs:
            df = read_table(path)

        self.assertEqual(list(df.columns), ["X", "X_2", "Coluna", "Y"])
        self.assertEqual(df.iloc[0].tolist(), [1, 2, 3, 4])
        self.assertIn("Cabeçalhos ajustados", "\n".join(logs.output))

    def test_cabecalhos_limpos_nao_geram_log(self):
        path = self.write("ok.csv", "A;B\n1;2\n")
        with self.assertNoLogs("finance_toolkit", level="WARNING"):
            df = read_table(path)
        self.assertEqual(list(df.columns), ["A", "B"])
