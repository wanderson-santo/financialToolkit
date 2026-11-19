"""Exportação padronizada para XLSX e CSV."""
from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

import pandas as pd
from openpyxl.utils import get_column_letter

NUMBER_FORMAT = "#,##0.00"


def _guard(value):
    # openpyxl grava texto iniciado por "=" como fórmula; neutraliza.
    if isinstance(value, str) and value.startswith("="):
        return "'" + value
    return value


def _protect(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in out.columns:
        s = out[col]
        if s.dtype == object or pd.api.types.is_string_dtype(s):
            out[col] = s.map(_guard)
    return out


def export_sheets(
    sheets: dict[str, pd.DataFrame],
    path,
    number_columns: dict[str, list[str]] | None = None,
    date_format: str = "DD/MM/YYYY",
) -> Path:
    """Grava um XLSX com cabeçalho congelado e largura de coluna ajustada."""
    path = Path(path)
    number_columns = number_columns or {}
    with pd.ExcelWriter(
        path, engine="openpyxl", date_format=date_format, datetime_format=f"{date_format} HH:MM:SS"
    ) as writer:
        for name, df in sheets.items():
            sheet_name = re.sub(r"[\[\]:*?/\\]", "-", name)[:31] or "Planilha"
            df = _protect(df)
            df.to_excel(writer, sheet_name=sheet_name, index=False)
            ws = writer.sheets[sheet_name]
            ws.freeze_panes = "A2"
            columns = list(df.columns)
            for idx, col in enumerate(columns, start=1):
                sample = [len(str(col))] + [len(str(x)) for x in df[col].head(200).tolist()]
                ws.column_dimensions[get_column_letter(idx)].width = min(max(sample) + 2, 60)
            for idx in range(1, len(columns) + 1):  # datas: formato dd/mm/aaaa nas células de data
                for row in range(2, ws.max_row + 1):
                    cell = ws.cell(row=row, column=idx)
                    if isinstance(cell.value, (date, datetime)):
                        cell.number_format = date_format
            for col in number_columns.get(name, []):
                if col in columns:
                    idx = columns.index(col) + 1
                    for row in range(2, ws.max_row + 1):
                        ws.cell(row=row, column=idx).number_format = NUMBER_FORMAT
    return path


def export_rows(rows: list[dict], path) -> Path:
    """Exporta uma lista de dicionários para .xlsx ou .csv (conforme a extensão)."""
    path = Path(path)
    df = pd.DataFrame(rows)
    if path.suffix.lower() == ".csv":
        df.to_csv(path, sep=";", index=False, encoding="utf-8-sig")
        return path
    return export_sheets({"Resultado": df}, path)
