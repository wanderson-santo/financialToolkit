import csv
import threading
import time
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

import pandas as pd
from openpyxl import load_workbook

from app.module_registry import build_registry
from core.exceptions import ToolkitError, ValidationError
from core.execution_context import ExecutionContext
from modules.files import duplicate_finder
from modules.files.company_folders import CompanyFolders
from modules.files.duplicate_finder import ACTION_MOVE, ACTION_REPORT, DuplicateFinder
from modules.files.folder_organizer import FolderOrganizer, parse_rules
from modules.finance.cnpj_validator import CnpjValidator
from modules.spreadsheets.cleaner import SheetCleaner
from modules.spreadsheets.comparator import SheetComparator, same_value
from tests.helpers import TempDirCase


class OrganizerTests(TempDirCase):
    def inputs(self, **kw):
        base = {"folder": str(self.tmp / "in"), "name_rules": "Bradesco=bradesco", "use_extensions": True,
                "ext_rules": "Docs=.pdf\nPlanilhas=.xlsx", "others_folder": "Outros"}
        base.update(kw)
        return base

    def test_preview_nao_move_e_execute_move(self):
        self.write("in/Extrato_Bradesco.pdf")
        self.write("in/nota.pdf")
        self.write("in/dados.xlsx")
        self.write("in/foto.png")
        self.write("in/desktop.ini")
        m = FolderOrganizer()
        r = m.preview(self.inputs(), self.ctx)
        dest = {d["Arquivo"]: d["Destino"] for d in r.details}
        self.assertEqual(dest["Extrato_Bradesco.pdf"], "Bradesco")  # nome vence extensão
        self.assertEqual(dest["nota.pdf"], "Docs")
        self.assertEqual(dest["foto.png"], "Outros")
        self.assertNotIn("desktop.ini", dest)
        self.assertTrue((self.tmp / "in" / "nota.pdf").exists())  # nada movido

        r = m.execute(self.inputs(), self.ctx)
        self.assertEqual((r.status, r.processed, r.errors), ("success", 4, 0))
        self.assertTrue((self.tmp / "in" / "Bradesco" / "Extrato_Bradesco.pdf").exists())
        self.assertFalse((self.tmp / "in" / "nota.pdf").exists())

    def test_conflito_nao_sobrescreve(self):
        self.write("in/a.pdf", b"novo")
        self.write("in/Docs/a.pdf", b"antigo")
        FolderOrganizer().execute(self.inputs(), self.ctx)
        self.assertEqual((self.tmp / "in/Docs/a.pdf").read_bytes(), b"antigo")
        self.assertEqual((self.tmp / "in/Docs/a_1.pdf").read_bytes(), b"novo")

    def test_regras_invalidas(self):
        with self.assertRaises(ValidationError):
            parse_rules("sem igual")
        issues = FolderOrganizer().validate(self.inputs(name_rules="ruim"))
        self.assertTrue(any(i.level == "error" for i in issues))


class _CancelAfterFirstMove(ExecutionContext):
    def __init__(self):
        self.event = threading.Event()
        super().__init__("test", cancel_event=self.event)

    def progress(self, current, total, step=""):
        super().progress(current, total, step)
        if step == "Movendo duplicatas" and current == 1:
            self.event.set()


class DuplicateTests(TempDirCase):
    def move_inputs(self):
        return {"folder": str(self.tmp / "p"), "recursive": True, "action": ACTION_MOVE,
                "keep": "Mais antigo (data de modificação)", "quarantine": "_q"}

    def test_manifesto_existe_antes_do_primeiro_move(self):
        self.write("p/a.txt", b"mesmo conteudo")
        time.sleep(0.02)
        self.write("p/sub/b.txt", b"mesmo conteudo")
        seen = []
        real_move = duplicate_finder.move_to

        def checked_move(src, dest):
            manifests = list(Path(dest).parent.glob("manifesto_*.csv"))
            seen.append(bool(manifests))
            self.assertEqual(len(manifests), 1)
            with manifests[0].open(encoding="utf-8-sig", newline="") as fh:
                rows = list(csv.reader(fh, delimiter=";"))
            self.assertEqual(rows[0], ["grupo", "origem", "destino", "status"])
            self.assertTrue(any(row[1] == str(src) and row[2] == str(dest) for row in rows[1:]))
            return real_move(src, dest)

        with mock.patch.object(duplicate_finder, "move_to", new=checked_move):
            r = DuplicateFinder().execute(self.move_inputs(), self.ctx)

        self.assertEqual(seen, [True])
        self.assertEqual(r.processed, 1)
        with Path(r.output_files[0]).open(encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.reader(fh, delimiter=";"))
        moved = [row for row in rows[1:] if row[3] == "movida"]
        self.assertEqual(len(moved), 1)
        self.assertEqual(moved[0][1], str(self.tmp / "p/sub/b.txt"))
        self.assertEqual(moved[0][2], str(self.tmp / "p/_q/b.txt"))

    def test_falha_ao_gravar_manifesto_aborta_antes_de_mover(self):
        self.write("p/a.txt", b"mesmo conteudo")
        time.sleep(0.02)
        self.write("p/sub/b.txt", b"mesmo conteudo")
        with mock.patch.object(duplicate_finder, "_write_manifest", side_effect=OSError("disco cheio")):
            with self.assertRaises(ToolkitError) as ctx:
                DuplicateFinder().execute(self.move_inputs(), self.ctx)

        self.assertIn("Nenhum arquivo foi movido", str(ctx.exception))
        self.assertTrue((self.tmp / "p/a.txt").exists())
        self.assertTrue((self.tmp / "p/sub/b.txt").exists())
        self.assertEqual(list((self.tmp / "p/_q").glob("*.txt")), [])

    def test_cancelamento_apos_primeiro_move_preserva_manifesto(self):
        for name in ("a.txt", "b.txt", "c.txt"):
            self.write(f"p/{name}", b"mesmo conteudo")
            time.sleep(0.02)
        r = DuplicateFinder().execute(self.move_inputs(), _CancelAfterFirstMove())

        self.assertEqual((r.status, r.processed), ("cancelled", 1))
        with Path(r.output_files[0]).open(encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.reader(fh, delimiter=";"))
        statuses = sorted(row[3] for row in rows[1:])
        self.assertEqual(statuses, ["cancelado", "movida"])
        self.assertEqual(len(list((self.tmp / "p/_q").glob("*.txt"))), 1)
        self.assertEqual(len(list((self.tmp / "p").glob("*.txt"))), 2)

    def test_relatar_e_mover(self):
        self.write("p/a.txt", b"mesmo conteudo")
        time.sleep(0.02)
        self.write("p/sub/b.txt", b"mesmo conteudo")
        self.write("p/c.txt", b"outro")
        self.write("p/vazio1.txt", b"")
        m = DuplicateFinder()
        inp = {"folder": str(self.tmp / "p"), "recursive": True, "action": ACTION_REPORT,
               "keep": "Mais antigo (data de modificação)", "quarantine": "_q"}
        r = m.execute(inp, self.ctx)
        self.assertEqual(r.processed, 1)
        self.assertTrue((self.tmp / "p/sub/b.txt").exists())  # só relatou

        inp["action"] = ACTION_MOVE
        r = m.execute(inp, self.ctx)
        self.assertEqual((r.status, r.processed), ("success", 1))
        self.assertTrue((self.tmp / "p/a.txt").exists())          # o mais antigo fica
        self.assertFalse((self.tmp / "p/sub/b.txt").exists())
        self.assertTrue((self.tmp / "p/_q/b.txt").exists())
        self.assertEqual(len(r.output_files), 1)                   # manifesto
        # a quarentena não é varrida na execução seguinte
        r2 = m.preview(inp, self.ctx)
        self.assertEqual(r2.processed, 0)


class CompanyFoldersTests(TempDirCase):
    def test_cria_so_ativas(self):
        df = pd.DataFrame({
            "Razão Social": ["BB EMPREENDIMENTOS E PARTICIPACOES SA ", "Banco do Brasil S.A.", "Alfa Ltda",
                             "BB PARTICIPACOES SA", None, "Zeta Comercio ME"],
            "Situação Cadastral": ["ATIVA", "Ativa", "BAIXADA", "ATIVA", "ATIVA", "suspensa"],
        })
        xlsx = self.tmp / "empresas.xlsx"
        df.to_excel(xlsx, index=False)
        target = self.tmp / "dest"
        target.mkdir()
        inp = {"spreadsheet": str(xlsx), "sheet": "", "name_column": "Razão Social",
               "status_column": "Situação Cadastral", "active_values": "ATIVA, ATIVO",
               "target_folder": str(target), "cut_words": "SA, LTDA, EMPREENDIMENTOS, PARTICIPACOES"}
        m = CompanyFolders()
        r = m.preview(inp, self.ctx)
        self.assertEqual(sorted(d["Pasta"] for d in r.details), ["BANCO DO BRASIL", "BB"])
        self.assertEqual(list(target.iterdir()), [])
        r = m.execute(inp, self.ctx)
        self.assertEqual(sorted(p.name for p in target.iterdir()), ["BANCO DO BRASIL", "BB"])
        self.assertEqual(r.warnings, 1)  # linha ativa sem nome
        r = m.execute(inp, self.ctx)      # segunda vez: já existem
        self.assertTrue(all(d["Resultado"] == "Já existia" for d in r.details))


class CleanerTests(TempDirCase):
    def test_limpeza_com_cabecalhos_repetidos(self):
        path = self.write("dup.csv", "X; X ;;Y\n1;2;3;4\n")
        inp = {"spreadsheet": str(path), "sheet": "", "remove_empty": True, "clean_text": True,
               "normalize_headers": False, "cnpj_cols": [], "date_cols": [], "value_cols": [],
               "number_format": "Brasileiro (1.234,56)", "output_folder": ""}
        r = SheetCleaner().execute(inp, self.ctx)
        ws = load_workbook(r.output_files[0]).active
        self.assertEqual([c.value for c in ws[1]], ["X", "X_2", "Coluna", "Y"])
        self.assertEqual([c.value for c in ws[2]], ["1", "2", "3", "4"])

    def test_limpeza_completa(self):
        df = pd.DataFrame({
            " CNPJ ": [11222333000181, "11.222.333/0001-81 ", "invalido", None, None],
            "Data": ["31/01/2024", "2024-02-15", "nao-data", None, None],
            "Valor": ["1.234,56", "R$ 10,00", "x", None, None],
            "Nome": ["  Ana\u00a0Silva ", "Bia", "Caio", None, None],
            "Vazia": [None] * 5,
        })
        xlsx = self.tmp / "dados.xlsx"
        df.to_excel(xlsx, index=False)
        inp = {"spreadsheet": str(xlsx), "sheet": "", "remove_empty": True, "clean_text": True,
               "normalize_headers": True, "cnpj_cols": ["CNPJ"], "date_cols": ["Data"],
               "value_cols": ["Valor"], "number_format": "Brasileiro (1.234,56)", "output_folder": ""}
        original_bytes = xlsx.read_bytes()
        m = SheetCleaner()
        r = m.preview(inp, self.ctx)
        self.assertEqual(r.warnings, 3)
        self.assertFalse((self.tmp / "dados_limpo.xlsx").exists())

        r = m.execute(inp, self.ctx)
        out = Path(r.output_files[0])
        self.assertEqual(out.name, "dados_limpo.xlsx")
        ws = load_workbook(out).active
        header = [c.value for c in ws[1]]
        self.assertEqual(header, ["CNPJ", "Data", "Valor", "Nome"])  # coluna vazia saiu, cabeçalho limpo
        self.assertEqual(ws.max_row, 4)                              # 3 linhas + cabeçalho (2 vazias saíram)
        self.assertEqual(ws["A2"].value, "11.222.333/0001-81")
        self.assertEqual(ws["A3"].value, "11.222.333/0001-81")
        self.assertEqual(ws["A4"].value, "invalido")
        self.assertEqual(ws["B2"].value.date(), date(2024, 1, 31))
        self.assertEqual(ws["B2"].number_format, "DD/MM/YYYY")
        self.assertEqual(ws["C2"].value, 1234.56)
        self.assertEqual(ws["C3"].value, 10.0)
        self.assertEqual(ws["C2"].number_format, "#,##0.00")
        self.assertEqual(ws["D2"].value, "Ana Silva")
        # original intacto
        self.assertEqual(xlsx.read_bytes(), original_bytes)


class ComparatorTests(TempDirCase):
    def test_same_value(self):
        self.assertTrue(same_value("1.234,50", "1234.5"))
        self.assertTrue(same_value("ABC", "abc"))
        self.assertFalse(same_value("ABC", "abc", ignore_case=False))
        self.assertTrue(same_value(10.004, 10.0, tolerance=0.01))
        self.assertFalse(same_value(10.02, 10.0, tolerance=0.01))
        self.assertTrue(same_value("10.01", "10.00", tolerance=0.01))
        self.assertFalse(same_value("10.02", "10.00", tolerance=0.01))
        self.assertTrue(same_value(None, ""))

    def test_numeros_brasileiros(self):
        cases = [
            ("1.234", "1234"),
            ("12.345", "12345"),
            ("1.234.567", "1234567"),
            ("1.234,00", "1234"),
            ("R$ 1.234", "1234"),
            ("R$ 1.234,56", "1234.56"),
            ("-1.234", "-1234"),
            ("(1.234)", "-1234"),
            ("1.234-", "-1234"),
            ("1,23", "1.23"),
            ("1.23", "1,23"),
            ("1.2345", "1.2345"),
        ]
        for a, b in cases:
            with self.subTest(a=a, b=b):
                self.assertTrue(same_value(a, b))

        # Valores numéricos não são reinterpretados como texto.
        self.assertTrue(same_value(1.234, 1.234))
        self.assertFalse(same_value(1.234, 1234))
        # Formatos fora do padrão de milhar não são convertidos.
        self.assertFalse(same_value("1.234", "1.2345"))
        self.assertFalse(same_value("1.2.3", "123"))

    def test_tolerancia_formatos_inequivocos(self):
        cases = {
            "0": 0.0,
            "0,01": 0.01,
            "0.01": 0.01,
            "1.000,00": 1000.0,
            "1.000.000": 1_000_000.0,
            "R$ 0,05": 0.05,
            "1,234.56": 1234.56,
            "": 0.0,
            None: 0.0,
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertAlmostEqual(SheetComparator._tolerance({"tolerance": text}), expected)

        messages = [i.message for i in SheetComparator().validate({"tolerance": "0.01"})]
        self.assertFalse(any("tolerância" in msg.casefold() for msg in messages), messages)

    def test_tolerancia_ambigua_ou_invalida(self):
        for text in ("1.000", "1.234", "0.001"):
            with self.subTest(text=text):
                with self.assertRaises(ValidationError):
                    SheetComparator._tolerance({"tolerance": text})
                messages = [i.message for i in SheetComparator().validate({"tolerance": text})]
                self.assertTrue(any("ambígua" in msg for msg in messages), messages)

        for text in ("abc", "1,2,3", "-0,01"):
            with self.subTest(text=text):
                with self.assertRaises(ValidationError):
                    SheetComparator._tolerance({"tolerance": text})

        messages = [i.message for i in SheetComparator().validate({"tolerance": "abc"})]
        self.assertTrue(any("inválida" in msg for msg in messages), messages)

    def test_tolerancia_0_01_nao_ignora_50_centavos(self):
        a = pd.DataFrame({"CNPJ": ["1"], "Valor": [10.00]})
        b = pd.DataFrame({"CNPJ": ["1"], "Valor": [10.50]})
        fa, fb = self.tmp / "tol_a.xlsx", self.tmp / "tol_b.xlsx"
        a.to_excel(fa, index=False)
        b.to_excel(fb, index=False)
        inp = {"file_a": str(fa), "file_b": str(fb), "keys": ["CNPJ"], "compare_cols": [],
               "ignore_case": True, "tolerance": "0.01", "output_folder": ""}
        m = SheetComparator()
        kinds = [(d["Tipo"], d["Chave"], d["Coluna"]) for d in m.preview(inp, self.ctx).details]
        self.assertIn(("Alterado", "1", "Valor"), kinds)

        inp["tolerance"] = "0,50"
        kinds = [(d["Tipo"], d["Chave"], d["Coluna"]) for d in m.preview(inp, self.ctx).details]
        self.assertNotIn(("Alterado", "1", "Valor"), kinds)

    def test_comparacao_inteiros_br(self):
        a = pd.DataFrame({"CNPJ": ["1", "2", "3"], "Valor": ["1.234", "1.234.567", "R$ 1.234"]})
        b = pd.DataFrame({"CNPJ": ["1", "2", "3"], "Valor": [1234, 1234567, 1235]})
        fa, fb = self.tmp / "br_a.xlsx", self.tmp / "br_b.xlsx"
        a.to_excel(fa, index=False)
        b.to_excel(fb, index=False)
        inp = {"file_a": str(fa), "file_b": str(fb), "keys": ["CNPJ"], "compare_cols": [],
               "ignore_case": True, "tolerance": "0", "output_folder": ""}
        kinds = [(d["Tipo"], d["Chave"], d["Coluna"])
                 for d in SheetComparator().preview(inp, self.ctx).details]
        self.assertNotIn(("Alterado", "1", "Valor"), kinds)
        self.assertNotIn(("Alterado", "2", "Valor"), kinds)
        self.assertIn(("Alterado", "3", "Valor"), kinds)

    def test_comparacao(self):
        a = pd.DataFrame({"CNPJ": ["1", "2", "3", "3"], "Nome": ["Ana", "Bia", "Caio", "Dup"], "Valor": [10, 20, 30, 1]})
        b = pd.DataFrame({"CNPJ": ["1", "2", "4"], "Nome": ["Ana", "BIANCA", "Dora"], "Valor": [10.0, 25, 40]})
        fa, fb = self.tmp / "a.xlsx", self.tmp / "b.xlsx"
        a.to_excel(fa, index=False)
        b.to_excel(fb, index=False)
        inp = {"file_a": str(fa), "file_b": str(fb), "keys": ["CNPJ"], "compare_cols": [],
               "ignore_case": True, "tolerance": "0", "output_folder": ""}
        m = SheetComparator()
        r = m.preview(inp, self.ctx)
        kinds = [(d["Tipo"], d["Chave"], d["Coluna"]) for d in r.details]
        self.assertIn(("Incluído", "4", ""), kinds)
        self.assertIn(("Removido", "3", ""), kinds)
        self.assertIn(("Alterado", "2", "Nome"), kinds)
        self.assertIn(("Alterado", "2", "Valor"), kinds)
        self.assertNotIn(("Alterado", "1", "Valor"), kinds)  # 10 == 10.0
        self.assertEqual(r.warnings, 1)                       # chave repetida em A

        r = m.execute(inp, self.ctx)
        wb = load_workbook(r.output_files[0])
        self.assertEqual(wb.sheetnames, ["Resumo", "Incluídos", "Removidos", "Alterados", "Avisos"])
        self.assertEqual(wb["Alterados"].max_row, 3)

    def test_comparacao_com_cabecalhos_repetidos(self):
        fa = self.write("dup_a.csv", "CNPJ;Valor; Valor\n1;10;100\n")
        fb = self.write("dup_b.csv", "CNPJ;Valor; Valor\n1;10;200\n")
        inp = {"file_a": str(fa), "file_b": str(fb), "keys": ["CNPJ"], "compare_cols": [],
               "ignore_case": True, "tolerance": "0", "output_folder": ""}
        m = SheetComparator()
        r = m.preview(inp, self.ctx)
        kinds = [(d["Tipo"], d["Chave"], d["Coluna"]) for d in r.details]
        self.assertIn(("Alterado", "1", "Valor_2"), kinds)
        self.assertNotIn(("Alterado", "1", "Valor"), kinds)
        self.assertEqual(r.warnings, 0)

        r = m.execute(inp, self.ctx)
        wb = load_workbook(r.output_files[0])
        self.assertEqual(wb["Alterados"].max_row, 2)  # cabeçalho + a célula alterada

    def test_chave_ausente(self):
        fa = self.tmp / "a.xlsx"
        pd.DataFrame({"X": [1]}).to_excel(fa, index=False)
        inp = {"file_a": str(fa), "file_b": str(fa), "keys": ["CNPJ"], "tolerance": "0"}
        with self.assertRaises(ValidationError):
            SheetComparator().preview(inp, self.ctx)


class CnpjModuleTests(TempDirCase):
    def test_valida_e_exporta(self):
        df = pd.DataFrame({"CNPJ": ["11.222.333/0001-81", "11222333000182", "", "11222333000181"], "Nome": list("abcd")})
        xlsx = self.tmp / "c.xlsx"
        df.to_excel(xlsx, index=False)
        inp = {"spreadsheet": str(xlsx), "sheet": "", "column": "CNPJ", "output_folder": ""}
        m = CnpjValidator()
        r = m.preview(inp, self.ctx)
        status = [d["Situação"] for d in r.details]
        self.assertEqual(status, ["Válido", "Dígitos verificadores inválidos", "Vazio", "Válido"])
        self.assertEqual(r.details[0]["Duplicado nas linhas"], "2, 5")
        r = m.execute(inp, self.ctx)
        out = pd.read_excel(r.output_files[0], dtype=str)
        self.assertEqual(list(out.columns)[-3:], ["CNPJ_Formatado", "CNPJ_Situacao", "CNPJ_Duplicado_Linhas"])


class RegistryTests(unittest.TestCase):
    def test_ids_unicos_e_params(self):
        reg = build_registry()
        ids = [m.module_id for m in reg.modules()] + [p.module_id for p in reg.planned()]
        self.assertEqual(len(ids), len(set(ids)))
        for m in reg.modules():
            keys = [p.key for p in m.params]
            self.assertEqual(len(keys), len(set(keys)), m.module_id)
            for p in m.params:
                if p.kind in ("column", "columns"):
                    self.assertIn(p.source, keys)
                if p.kind == "choice":
                    self.assertTrue(p.choices)


if __name__ == "__main__":
    unittest.main()
