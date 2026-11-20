"""Exportação padronizada para XLSX e CSV."""
from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

import pandas as pd
from openpyxl.utils import get_column_letter

from .normalizers import parse_number

NUMBER_FORMAT = "#,##0.00"

_INVALID_SHEET_CHARS = re.compile(r"[\[\]:*?/\\]")
_MAX_SHEET_NAME = 31


def _sheet_base_name(name: str) -> str:
    """Sanitiza e trunca um nome de aba sem ainda considerar colisões."""
    clean = _INVALID_SHEET_CHARS.sub("-", str(name or ""))[:_MAX_SHEET_NAME]
    return clean or "Planilha"


def _unique_sheet_names(names) -> dict[str, str]:
    """Mapeia cada chave para um nome de aba único, preservando a ordem.

    A comparação ignora maiúsculas/minúsculas porque o Excel não diferencia
    ``Dados`` de ``dados``. Colisões recebem ``_2``, ``_3``… sem ultrapassar
    31 caracteres.
    """
    used: set[str] = set()
    mapping: dict[str, str] = {}
    for name in names:
        base = _sheet_base_name(name)
        candidate = base
        counter = 2
        while candidate.casefold() in used:
            suffix = f"_{counter}"
            candidate = base[: _MAX_SHEET_NAME - len(suffix)] + suffix
            counter += 1
        used.add(candidate.casefold())
        mapping[name] = candidate
    return mapping


_INVISIBLE_START = "\ufeff\u200b\u200c\u200d\u2060\u00ad"


def _is_numeric_text(text: str) -> bool:
    """True se o texto inteiro representa um número (inclusive negativo)."""
    return parse_number(text, "br") is not None or parse_number(text, "intl") is not None


def _is_dangerous(text: str) -> bool:
    """Detecta conteúdo que pode ser interpretado como fórmula por planilhas.

    A verificação ignora espaços à esquerda, mas preserva o valor original.
    Números legítimos iniciados por ``+`` ou ``-`` não são tratados como
    fórmulas.
    """
    if text and (ord(text[0]) < 32 or text[0] in _INVISIBLE_START):
        return True
    stripped = text.lstrip()
    while stripped and (ord(stripped[0]) < 32 or stripped[0] in _INVISIBLE_START):
        stripped = stripped[1:].lstrip()
    if not stripped:
        return False
    first = stripped[0]
    if first in ("=", "@"):
        return True
    if first in ("+", "-"):
        return not _is_numeric_text(stripped)
    return False


def _guard(value):
    """Prefixa apóstrofo em textos perigosos para que sejam exportados como texto."""
    if isinstance(value, str) and _is_dangerous(value):
        return "'" + value
    return value


def _protect(df: pd.DataFrame) -> pd.DataFrame:
    """Sanitiza valores e cabeçalhos antes de qualquer exportação tabular."""
    out = df.copy()
    out.columns = [_guard(col) for col in out.columns]
    for idx in range(out.shape[1]):
        s = out.iloc[:, idx]
        if s.dtype == object or pd.api.types.is_string_dtype(s):
            out.isetitem(idx, s.map(_guard))
    return out


def export_sheets(
    sheets: dict[str, pd.DataFrame],
    path,
    number_columns: dict[str, list[str]] | None = None,
    date_format: str = "DD/MM/YYYY",
) -> Path:
    """Grava um XLSX com cabeçalho congelado e largura de coluna ajustada.

    Nomes de aba são sanitizados, truncados em 31 caracteres e deduplicados
    (``nome``, ``nome_2``…), inclusive quando diferem apenas por maiúsculas.

    Toda célula textual passa por :func:`_protect`: conteúdo que poderia ser
    interpretado como fórmula recebe um apóstrofo inicial. Números nativos não
    são alterados.
    """
    path = Path(path)
    number_columns = number_columns or {}
    sheet_names = _unique_sheet_names(sheets)
    with pd.ExcelWriter(
        path, engine="openpyxl", date_format=date_format, datetime_format=f"{date_format} HH:MM:SS"
    ) as writer:
        for name, df in sheets.items():
            sheet_name = sheet_names[name]
            original_columns = list(df.columns)
            df = _protect(df)
            df.to_excel(writer, sheet_name=sheet_name, index=False)
            ws = writer.sheets[sheet_name]
            ws.freeze_panes = "A2"
            columns = list(df.columns)
            for idx, col in enumerate(columns, start=1):
                values = df.iloc[:, idx - 1].head(200).tolist()
                sample = [len(str(col))] + [len(str(x)) for x in values]
                ws.column_dimensions[get_column_letter(idx)].width = min(max(sample) + 2, 60)
            for idx in range(1, len(columns) + 1):  # datas: formato dd/mm/aaaa nas células de data
                for row in range(2, ws.max_row + 1):
                    cell = ws.cell(row=row, column=idx)
                    if isinstance(cell.value, (date, datetime)):
                        cell.number_format = date_format
            for col in number_columns.get(name, []):
                if col in original_columns:
                    idx = original_columns.index(col) + 1
                elif col in columns:
                    idx = columns.index(col) + 1
                else:
                    continue
                for row in range(2, ws.max_row + 1):
                    ws.cell(row=row, column=idx).number_format = NUMBER_FORMAT
    return path


def export_rows(rows: list[dict], path) -> Path:
    """Exporta uma lista de dicionários para .xlsx ou .csv (conforme a extensão).

    A mesma política de sanitização é aplicada aos dois formatos; no CSV, o
    apóstrofo inicial é o que impede a planilha de interpretar a célula como
    fórmula.
    """
    path = Path(path)
    df = _protect(pd.DataFrame(rows))
    if path.suffix.lower() == ".csv":
        df.to_csv(path, sep=";", index=False, encoding="utf-8-sig")
        return path
    return export_sheets({"Resultado": df}, path)
