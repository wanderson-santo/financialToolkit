"""Limpador e padronizador de planilhas.

Gera uma NOVA planilha (`<nome>_limpo.xlsx`); o arquivo original nunca é alterado.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from core.base_module import BaseModule, Issue, ParamSpec, Result, build_result
from core.categories import CATEGORY_SHEETS
from core.export_service import export_sheets
from core.file_service import resolve_output_dir, unique_path
from core.normalizers import (
    clean_text, format_cnpj, is_blank, normalize_cnpj, parse_date, parse_number,
)
from core.spreadsheet_service import SHEET_FILETYPES, read_table, unique_headers

FMT_BR = "Brasileiro (1.234,56)"
FMT_INTL = "Internacional (1,234.56)"


def clean_table(df: pd.DataFrame, opts: dict) -> tuple[pd.DataFrame, list[dict], int, list[str]]:
    """Aplica as limpezas pedidas. Devolve (df, estatísticas, avisos, colunas numéricas)."""
    # Acesso posicional: funciona mesmo se o DataFrame trouxer rótulos repetidos.
    headers = unique_headers(df.columns)
    data = {name: df.iloc[:, i].tolist() for i, name in enumerate(headers)}
    stats: list[dict] = []
    warnings = 0
    rows_in, cols_in = len(df), len(df.columns)

    def note(op: str, col: str, count: int):
        if count:
            stats.append({"Operação": op, "Coluna": col, "Células afetadas": count})

    if opts["clean_text"]:
        for col, vals in data.items():
            new = [clean_text(v) if isinstance(v, str) else v for v in vals]
            note("Texto limpo (espaços/invisíveis)", col,
                 sum(1 for a, b in zip(vals, new) if isinstance(a, str) and a != b))
            data[col] = new

    for col in opts["cnpj_cols"]:
        new, changed, invalid = [], 0, 0
        for v in data[col]:
            if is_blank(v):
                new.append(v)
                continue
            digits = normalize_cnpj(v)
            if digits is None:
                invalid += 1
                new.append(v)
                continue
            formatted = format_cnpj(digits)
            changed += formatted != v
            new.append(formatted)
        data[col] = new
        note("CNPJ formatado", col, changed)
        if invalid:
            warnings += invalid
            note("⚠ CNPJ não reconhecido (mantido como veio)", col, invalid)

    for col in opts["date_cols"]:
        new, changed, invalid = [], 0, 0
        for v in data[col]:
            if is_blank(v):
                new.append(v)
                continue
            d = parse_date(v)
            if d is None:
                invalid += 1
                new.append(v)
                continue
            changed += v != d
            new.append(d)
        data[col] = new
        note("Convertido para data", col, changed)
        if invalid:
            warnings += invalid
            note("⚠ Data não reconhecida (mantida como veio)", col, invalid)

    number_cols: list[str] = []
    fmt = "br" if opts["number_format"] == FMT_BR else "intl"
    for col in opts["value_cols"]:
        new, changed, invalid = [], 0, 0
        for v in data[col]:
            if is_blank(v):
                new.append(v)
                continue
            n = parse_number(v, fmt)
            if n is None:
                invalid += 1
                new.append(v)
                continue
            changed += not isinstance(v, (int, float))
            new.append(n)
        data[col] = new
        number_cols.append(col)
        note("Convertido para número", col, changed)
        if invalid:
            warnings += invalid
            note("⚠ Valor não reconhecido (mantido como veio)", col, invalid)

    if opts["remove_empty"]:
        keep_rows = [i for i in range(rows_in) if any(not is_blank(vals[i]) for vals in data.values())]
        if len(keep_rows) < rows_in:
            note("Linhas vazias removidas", "(todas)", rows_in - len(keep_rows))
        data = {c: [v[i] for i in keep_rows] for c, v in data.items()}
        empty_cols = [c for c, v in data.items() if all(is_blank(x) for x in v)]
        for c in empty_cols:
            data.pop(c)
        note("Colunas vazias removidas", ", ".join(empty_cols), len(empty_cols))
        number_cols = [c for c in number_cols if c in data]

    if opts["normalize_headers"]:
        old_names = list(data)
        new_names = unique_headers([clean_text(n) for n in old_names])
        renamed = {o: n for o, n in zip(old_names, new_names)}
        note("Cabeçalhos padronizados", "(cabeçalho)", sum(o != n for o, n in renamed.items()))
        data = {renamed[c]: v for c, v in data.items()}
        number_cols = [renamed[c] for c in number_cols if c in renamed]

    out = pd.DataFrame({c: pd.Series(v, dtype=object) for c, v in data.items()})
    stats.append({"Operação": "Resultado final", "Coluna": f"{rows_in}→{len(out)} linhas, {cols_in}→{len(out.columns)} colunas",
                  "Células afetadas": ""})
    return out, stats, warnings, number_cols


class SheetCleaner(BaseModule):
    module_id = "sheet_cleaner"
    name = "Limpador e padronizador de planilhas"
    category = CATEGORY_SHEETS
    description = (
        "Remove linhas e colunas vazias, limpa espaços e caracteres invisíveis, padroniza cabeçalhos e "
        "converte colunas de CNPJ, datas e valores. Gera uma nova planilha; o original é preservado."
    )
    params = [
        ParamSpec("spreadsheet", "Planilha de entrada", "file", filetypes=SHEET_FILETYPES),
        ParamSpec("sheet", "Aba (vazio = primeira)", "text", required=False),
        ParamSpec("remove_empty", "Remover linhas e colunas vazias", "bool", default=True),
        ParamSpec("clean_text", "Limpar espaços e caracteres invisíveis nos textos", "bool", default=True),
        ParamSpec("normalize_headers", "Padronizar nomes das colunas (espaços)", "bool", default=True),
        ParamSpec("cnpj_cols", "Colunas de CNPJ (formatar 00.000.000/0000-00)", "columns", source="spreadsheet",
                  required=False, default="CNPJ"),
        ParamSpec("date_cols", "Colunas de data (converter para data do Excel)", "columns", source="spreadsheet",
                  required=False, default="Data"),
        ParamSpec("value_cols", "Colunas de valor (converter para número)", "columns", source="spreadsheet",
                  required=False, default="Valor"),
        ParamSpec("number_format", "Formato dos números em texto", "choice", default=FMT_BR, choices=[FMT_BR, FMT_INTL]),
        ParamSpec("output_folder", "Pasta de saída (vazio = mesma do original)", "folder", required=False),
    ]

    def validate(self, inputs: dict) -> list[Issue]:
        issues = super().validate(inputs)
        picked = [c for k in ("cnpj_cols", "date_cols", "value_cols") for c in (inputs.get(k) or [])]
        if len(picked) != len(set(picked)):
            issues.append(Issue.error("Uma mesma coluna não pode ser marcada em mais de um tipo de conversão."))
        return issues

    def _run(self, inputs: dict, ctx):
        ctx.progress(0, 3, "Lendo planilha")
        df = read_table(inputs["spreadsheet"], inputs.get("sheet") or None)
        ctx.log(f"Planilha lida: {len(df)} linha(s), {len(df.columns)} coluna(s).")
        ctx.check_cancel()
        opts = {
            "remove_empty": bool(inputs.get("remove_empty")),
            "clean_text": bool(inputs.get("clean_text")),
            "normalize_headers": bool(inputs.get("normalize_headers")),
            "cnpj_cols": [c for c in (inputs.get("cnpj_cols") or []) if c in df.columns],
            "date_cols": [c for c in (inputs.get("date_cols") or []) if c in df.columns],
            "value_cols": [c for c in (inputs.get("value_cols") or []) if c in df.columns],
            "number_format": inputs.get("number_format") or FMT_BR,
        }
        ctx.progress(1, 3, "Limpando dados")
        cleaned, stats, warnings, number_cols = clean_table(df, opts)
        ctx.check_cancel()
        return cleaned, stats, warnings, number_cols

    def preview(self, inputs: dict, ctx) -> Result:
        cleaned, stats, warnings, _ = self._run(inputs, ctx)
        ctx.progress(3, 3, "Pronto")
        return build_result(
            f"Pré-visualização: {len(stats) - 1} ajuste(s) previstos; resultado teria {len(cleaned)} linha(s) "
            f"e {len(cleaned.columns)} coluna(s). Nada foi gravado.",
            processed=len(cleaned), warnings=warnings, details=stats,
        )

    def execute(self, inputs: dict, ctx) -> Result:
        cleaned, stats, warnings, number_cols = self._run(inputs, ctx)
        ctx.progress(2, 3, "Gravando planilha")
        src = Path(inputs["spreadsheet"])
        out_dir = resolve_output_dir(inputs.get("output_folder"), src)
        out_path = unique_path(out_dir / f"{src.stem}_limpo.xlsx")
        export_sheets({"Dados": cleaned}, out_path, number_columns={"Dados": number_cols})
        ctx.progress(3, 3, "Pronto")
        ctx.log(f"Planilha gravada em {out_path}")
        return build_result(
            f"Planilha limpa gravada: {out_path.name} ({len(cleaned)} linha(s), {len(cleaned.columns)} coluna(s)). "
            "O original não foi alterado.",
            processed=len(cleaned), warnings=warnings, output_files=[str(out_path)], details=stats,
        )
