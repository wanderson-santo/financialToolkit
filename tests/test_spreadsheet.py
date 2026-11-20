import pandas as pd

from core.exceptions import ToolkitError
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


class CsvDetectionTests(TempDirCase):
    def _read_logged(self, path, **kwargs):
        with self.assertLogs("finance_toolkit", level="INFO") as logs:
            df = read_table(path, **kwargs)
        return df, "\n".join(logs.output)

    def test_utf8_e_utf8_com_bom(self):
        for encoding in ("utf-8", "utf-8-sig"):
            with self.subTest(encoding=encoding):
                path = self.tmp / f"{encoding}.csv"
                path.write_bytes("Nome;Valor\nJoão;10\n".encode(encoding))
                df, log = self._read_logged(path)
                self.assertEqual(list(df.columns), ["Nome", "Valor"])
                self.assertEqual(df.loc[0, "Nome"], "João")
                self.assertIn("codificação utf-8-sig", log)

    def test_cp1252(self):
        path = self.tmp / "cp1252.csv"
        path.write_bytes("Nome;Valor\nJoão;10\n".encode("cp1252"))
        df, log = self._read_logged(path)
        self.assertEqual(df.loc[0, "Nome"], "João")
        self.assertIn("codificação cp1252", log)

    def test_latin1_como_ultimo_recurso(self):
        path = self.tmp / "latin1.csv"
        path.write_bytes(b"Nome;Valor\nAna\x81;10\n")  # 0x81 não existe em cp1252
        df, log = self._read_logged(path)
        self.assertEqual(df.loc[0, "Nome"], "Ana\x81")
        self.assertIn("codificação latin-1", log)

    def test_byte_invalido_depois_de_64kb(self):
        content = ("A;B\n" + "x;y\n" * 20000 + "João;1\n").encode("cp1252")
        path = self.tmp / "tardio.csv"
        path.write_bytes(content)
        self.assertGreater(len(content), 65536)
        df, log = self._read_logged(path)
        self.assertEqual(df.iloc[-1]["A"], "João")
        self.assertIn("codificação cp1252", log)

    def test_separadores_ponto_virgula_virgula_tab_e_pipe(self):
        for sep in (";", ",", "\t", "|"):
            with self.subTest(separator=sep):
                path = self.tmp / f"sep_{ord(sep)}.csv"
                path.write_text(
                    sep.join(["Nome", "Valor"]) + "\n" + sep.join(["João", "10"]) + "\n",
                    encoding="utf-8",
                )
                df = read_table(path)
                self.assertEqual(list(df.columns), ["Nome", "Valor"])
                self.assertEqual(df.loc[0, "Nome"], "João")

    def test_separador_dentro_de_aspas_nao_confunde(self):
        path = self.write(
            "aspas.csv",
            '"Nome, Completo, apelido";Valor\n"Ana, Maria, Silva";10\n',
        )
        df = read_table(path)
        self.assertEqual(list(df.columns), ["Nome, Completo, apelido", "Valor"])
        self.assertEqual(df.loc[0, "Nome, Completo, apelido"], "Ana, Maria, Silva")

    def test_arquivo_vazio_tem_mensagem_clara(self):
        path = self.write("vazio.csv", b"")
        with self.assertRaises(ToolkitError) as ctx:
            read_table(path)
        self.assertIn("vazio", str(ctx.exception))
        self.assertNotIsInstance(ctx.exception, UnicodeDecodeError)

    def test_apenas_cabecalho(self):
        df = read_table(self.write("cabecalho.csv", "Nome;Valor\n"))
        self.assertEqual(list(df.columns), ["Nome", "Valor"])
        self.assertEqual(len(df), 0)

    def test_codificacao_explicita(self):
        path = self.tmp / "explicita.csv"
        path.write_bytes("Nome;Valor\nJoão;10\n".encode("cp1252"))
        self.assertEqual(read_table(path, encoding="cp1252").loc[0, "Nome"], "João")
        with self.assertRaises(ToolkitError):
            read_table(path, encoding="utf-8")
        with self.assertRaises(ToolkitError):
            read_table(path, encoding="nao-existe")

    def test_separador_explicito(self):
        path = self.write("forcado.csv", "A|B;C\n1|2;3\n")
        self.assertEqual(list(read_table(path).columns), ["A|B", "C"])
        self.assertEqual(list(read_table(path, separator="|").columns), ["A", "B;C"])
