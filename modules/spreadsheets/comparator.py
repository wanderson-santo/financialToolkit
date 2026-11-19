"""Comparador de planilhas: o que foi incluído, removido ou alterado entre duas versões."""
from __future__ import annotations

import numbers
import re
from datetime import datetime
from pathlib import Path

import pandas as pd

from core.base_module import BaseModule, Issue, ParamSpec, Result, build_result
from core.categories import CATEGORY_SHEETS
from core.exceptions import ValidationError
from core.export_service import export_sheets
from core.file_service import resolve_output_dir, unique_path
from core.normalizers import as_text, parse_number
from core.spreadsheet_service import SHEET_FILETYPES, read_table

_BR_NUMBER = re.compile(r"-?\d{1,3}(\.\d{3})*,\d+|-?\d+,\d+")

_TOLERANCE_EXAMPLES = "0, 0,01, 0.01 ou 1.000,00"


def _invalid_tolerance(text: str) -> ValidationError:
    return ValidationError(f'Tolerância inválida: "{text}". Use {_TOLERANCE_EXAMPLES}.')


def parse_tolerance(value) -> float:
    """Interpreta a tolerância sem cair na ambiguidade de ``0.01``.

    Regras explícitas:

    - vazio/ausente: ``0``;
    - vírgula e ponto juntos: o último separador é o decimal
      (``1.234,56`` ou ``1,234.56``);
    - somente vírgula: decimal brasileiro (``0,01``);
    - somente ponto, com exatamente três dígitos após: **ambíguo** e rejeitado
      (``1.000`` pode ser mil ou um);
    - somente ponto, em outros casos: ponto decimal (``0.01``);
    - vários pontos válidos como milhar: ``1.000.000``;
    - negativo, NaN/infinito ou texto inválido: erro explícito.
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        return 0.0
    if isinstance(value, bool):
        raise _invalid_tolerance(as_text(value))
    if isinstance(value, numbers.Real):
        number = float(value)
        if number != number or number in (float("inf"), float("-inf")):
            raise _invalid_tolerance(as_text(value))
        if number < 0:
            raise ValidationError("A tolerância não pode ser negativa.")
        return number

    text = as_text(value).strip()
    if not text:
        return 0.0
    text = re.sub(r"(?i)r\$", "", text)
    text = re.sub(r"\s+", "", text)
    if text.startswith("(") and text.endswith(")"):
        raise ValidationError("A tolerância não pode ser negativa.")
    if text.startswith("-"):
        raise ValidationError("A tolerância não pode ser negativa.")
    if text.startswith("+"):
        text = text[1:]
    if not text:
        raise _invalid_tolerance(as_text(value))

    if re.fullmatch(r"\d+", text):
        number = float(text)
    elif "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            if not re.fullmatch(r"\d{1,3}(?:\.\d{3})*,\d+", text):
                raise _invalid_tolerance(as_text(value))
            number = float(text.replace(".", "").replace(",", "."))
        else:
            if not re.fullmatch(r"\d{1,3}(?:,\d{3})*\.\d+", text):
                raise _invalid_tolerance(as_text(value))
            number = float(text.replace(",", ""))
    elif "," in text:
        if text.count(",") != 1 or not re.fullmatch(r"\d+,\d+", text):
            raise _invalid_tolerance(as_text(value))
        number = float(text.replace(",", "."))
    elif "." in text:
        if text.count(".") > 1:
            if not re.fullmatch(r"\d{1,3}(?:\.\d{3})+", text):
                raise _invalid_tolerance(as_text(value))
            number = float(text.replace(".", ""))
        else:
            whole, fraction = text.split(".")
            if not whole.isdigit() or not fraction.isdigit():
                raise _invalid_tolerance(as_text(value))
            if len(fraction) == 3:
                raise ValidationError(
                    f'Tolerância ambígua: "{text}". Use vírgula para decimal '
                    f"(por exemplo, {text.replace('.', ',')}) ou 1.000,00 para milhar."
                )
            number = float(text)
    else:
        raise _invalid_tolerance(as_text(value))

    if number != number or number in (float("inf"), float("-inf")):
        raise _invalid_tolerance(as_text(value))
    return number


def _numeric(text: str) -> float | None:
    if not text:
        return None
    try:
        value = float(text)
    except ValueError:
        value = parse_number(text, "br") if _BR_NUMBER.fullmatch(text) else None
    if value is None or value != value or value in (float("inf"), float("-inf")):
        return None
    return value


def same_value(a, b, tolerance: float = 0.0, ignore_case: bool = True) -> bool:
    """Compara como texto normalizado; se ambos forem numéricos, usa a tolerância."""
    ta, tb = as_text(a), as_text(b)
    if ignore_case:
        ta, tb = ta.casefold(), tb.casefold()
    if ta == tb:
        return True
    na, nb = _numeric(ta), _numeric(tb)
    return na is not None and nb is not None and abs(na - nb) <= tolerance + 1e-9


class SheetComparator(BaseModule):
    module_id = "sheet_comparator"
    name = "Comparador de planilhas"
    category = CATEGORY_SHEETS
    description = (
        "Compara duas versões de uma planilha pela(s) coluna(s)-chave e aponta registros incluídos, "
        "removidos e alterados (célula a célula). Gera um relatório em Excel com as divergências."
    )
    params = [
        ParamSpec("file_a", "Versão anterior (A)", "file", filetypes=SHEET_FILETYPES),
        ParamSpec("file_b", "Versão nova (B)", "file", filetypes=SHEET_FILETYPES),
        ParamSpec("keys", "Coluna(s)-chave (identificam o registro)", "columns", source="file_a", default="CNPJ"),
        ParamSpec("compare_cols", "Colunas a comparar (vazio = todas em comum)", "columns", source="file_a",
                  required=False),
        ParamSpec("ignore_case", "Ignorar diferença de maiúsculas/minúsculas", "bool", default=True),
        ParamSpec("tolerance", "Tolerância para valores numéricos", "text", default="0", required=False,
                  help="Diferenças até este valor são ignoradas. Aceita 0,01 ou 0.01; "
                       "para milhar, use 1.000,00 (1.000 sozinho é ambíguo)."),
        ParamSpec("output_folder", "Pasta do relatório (vazio = pasta da versão B)", "folder", required=False),
    ]

    def validate(self, inputs: dict) -> list[Issue]:
        issues = super().validate(inputs)
        try:
            parse_tolerance(inputs.get("tolerance"))
        except ValidationError as exc:
            issues.append(Issue.error(str(exc)))
        return issues

    @staticmethod
    def _tolerance(inputs: dict) -> float:
        return parse_tolerance(inputs.get("tolerance"))

    def _compare(self, inputs: dict, ctx) -> dict:
        ctx.progress(0, 4, "Lendo as duas planilhas")
        df_a, df_b = read_table(inputs["file_a"]), read_table(inputs["file_b"])
        keys = list(inputs["keys"])
        missing = [f"{k} (em {tag})" for k in keys for tag, df in (("A", df_a), ("B", df_b)) if k not in df.columns]
        if missing:
            raise ValidationError("Coluna-chave ausente: " + "; ".join(missing))
        ctx.log(f"A: {len(df_a)} linha(s); B: {len(df_b)} linha(s).")

        common = [c for c in df_a.columns if c in df_b.columns and c not in keys]
        wanted = inputs.get("compare_cols") or []
        compare_cols = [c for c in common if c in wanted] if wanted else common
        only_a = [c for c in df_a.columns if c not in df_b.columns]
        only_b = [c for c in df_b.columns if c not in df_a.columns]
        notices: list[dict] = []
        if only_a:
            notices.append({"Aviso": "Colunas só na versão A (não comparadas)", "Detalhe": ", ".join(only_a)})
        if only_b:
            notices.append({"Aviso": "Colunas só na versão B (não comparadas)", "Detalhe": ", ".join(only_b)})

        ignore_case = bool(inputs.get("ignore_case", True))
        tolerance = self._tolerance(inputs)

        def index(df: pd.DataFrame, tag: str):
            rows: dict[str, dict] = {}
            order: dict[str, str] = {}
            dup, blank = 0, 0
            for record in df.to_dict("records"):
                parts = [as_text(record[k]) for k in keys]
                if not any(parts):
                    blank += 1
                    continue
                norm = " | ".join(p.casefold() if ignore_case else p for p in parts)
                if norm in rows:
                    dup += 1
                    continue
                rows[norm] = record
                order[norm] = " | ".join(parts)
            if dup:
                notices.append({"Aviso": f"Chaves repetidas na versão {tag} (usada só a primeira)", "Detalhe": str(dup)})
            if blank:
                notices.append({"Aviso": f"Linhas sem chave na versão {tag} (ignoradas)", "Detalhe": str(blank)})
            return rows, order

        rows_a, label_a = index(df_a, "A")
        ctx.check_cancel()
        rows_b, label_b = index(df_b, "B")
        ctx.progress(2, 4, "Comparando registros")

        removed = [k for k in rows_a if k not in rows_b]
        added = [k for k in rows_b if k not in rows_a]
        changes: list[dict] = []
        changed_keys = set()
        shared = [k for k in rows_a if k in rows_b]
        for i, k in enumerate(shared, start=1):
            if i % 500 == 0:
                ctx.check_cancel()
                ctx.progress(i, len(shared), "Comparando registros")
            for col in compare_cols:
                a, b = rows_a[k][col], rows_b[k][col]
                if not same_value(a, b, tolerance, ignore_case):
                    changed_keys.add(k)
                    changes.append({"Chave": label_a[k], "Coluna": col,
                                    "Valor anterior": as_text(a), "Valor novo": as_text(b)})
        return {
            "keys": keys, "compare_cols": compare_cols, "df_a": df_a, "df_b": df_b,
            "rows_a": rows_a, "rows_b": rows_b, "label_a": label_a, "label_b": label_b,
            "removed": removed, "added": added, "changes": changes, "changed_keys": changed_keys,
            "shared": len(shared), "notices": notices,
        }

    @staticmethod
    def _detail_rows(r: dict) -> list[dict]:
        rows = [{"Tipo": "Incluído", "Chave": r["label_b"][k], "Coluna": "", "Valor anterior": "", "Valor novo": ""}
                for k in r["added"]]
        rows += [{"Tipo": "Removido", "Chave": r["label_a"][k], "Coluna": "", "Valor anterior": "", "Valor novo": ""}
                 for k in r["removed"]]
        rows += [{"Tipo": "Alterado", **c} for c in r["changes"]]
        return rows

    @staticmethod
    def _summary(r: dict) -> str:
        return (f"{len(r['added'])} incluído(s), {len(r['removed'])} removido(s), "
                f"{len(r['changed_keys'])} registro(s) com alteração ({len(r['changes'])} célula(s)); "
                f"{r['shared'] - len(r['changed_keys'])} idêntico(s).")

    def preview(self, inputs: dict, ctx) -> Result:
        r = self._compare(inputs, ctx)
        return build_result("Pré-visualização: " + self._summary(r), processed=r["shared"] + len(r["added"]),
                            warnings=len(r["notices"]), details=self._detail_rows(r))

    def execute(self, inputs: dict, ctx) -> Result:
        r = self._compare(inputs, ctx)
        ctx.progress(3, 4, "Gravando relatório")
        added_rows = pd.DataFrame([r["rows_b"][k] for k in r["added"]], columns=r["df_b"].columns, dtype=object)
        removed_rows = pd.DataFrame([r["rows_a"][k] for k in r["removed"]], columns=r["df_a"].columns, dtype=object)
        summary = pd.DataFrame([
            {"Item": "Versão A", "Valor": Path(inputs["file_a"]).name},
            {"Item": "Versão B", "Valor": Path(inputs["file_b"]).name},
            {"Item": "Chave(s)", "Valor": ", ".join(r["keys"])},
            {"Item": "Colunas comparadas", "Valor": ", ".join(r["compare_cols"])},
            {"Item": "Incluídos", "Valor": len(r["added"])},
            {"Item": "Removidos", "Valor": len(r["removed"])},
            {"Item": "Registros alterados", "Valor": len(r["changed_keys"])},
            {"Item": "Células alteradas", "Valor": len(r["changes"])},
            {"Item": "Registros idênticos", "Valor": r["shared"] - len(r["changed_keys"])},
        ])
        changes = pd.DataFrame(r["changes"], columns=["Chave", "Coluna", "Valor anterior", "Valor novo"])
        sheets = {"Resumo": summary, "Incluídos": added_rows, "Removidos": removed_rows, "Alterados": changes}
        if r["notices"]:
            sheets["Avisos"] = pd.DataFrame(r["notices"])
        out_dir = resolve_output_dir(inputs.get("output_folder"), inputs["file_b"])
        out_path = unique_path(out_dir / f"comparacao_{datetime.now():%Y%m%d_%H%M%S}.xlsx")
        export_sheets(sheets, out_path)
        ctx.progress(4, 4, "Pronto")
        ctx.log(f"Relatório gravado em {out_path}")
        return build_result(self._summary(r) + f" Relatório: {out_path.name}.",
                            processed=r["shared"] + len(r["added"]), warnings=len(r["notices"]),
                            output_files=[str(out_path)], details=self._detail_rows(r))
