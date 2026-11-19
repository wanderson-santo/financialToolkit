"""Leitura de planilhas (XLSX, XLSM, XLS e CSV) com detecção de codificação e separador."""
from __future__ import annotations

import codecs
from pathlib import Path

import pandas as pd

from .exceptions import ToolkitError

SHEET_FILETYPES = [("Planilhas", "*.xlsx *.xlsm *.xls *.csv *.tsv *.txt"), ("Todos os arquivos", "*.*")]
_TEXT_EXT = {".csv", ".txt", ".tsv"}


def _csv_params(path: Path) -> tuple[str, str]:
    raw = path.read_bytes()[:65536]
    encoding, sample = "latin-1", ""
    for enc in ("utf-8-sig", "cp1252"):
        try:
            sample = codecs.getincrementaldecoder(enc)().decode(raw, final=False)
            encoding = enc
            break
        except UnicodeDecodeError:
            continue
    else:
        sample = raw.decode("latin-1")
    first = sample.splitlines()[0] if sample else ""
    counts = {sep: first.count(sep) for sep in (";", ",", "\t", "|")}
    separator = max(counts, key=counts.get) if any(counts.values()) else ";"
    return encoding, separator


def read_table(path, sheet: str | None = None, nrows: int | None = None) -> pd.DataFrame:
    """Lê a planilha preservando tipos nativos do Excel (dtype=object).

    CSV é lido todo como texto. Os nomes das colunas viram `str`.
    """
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {p}")
    ext = p.suffix.lower()
    try:
        if ext in _TEXT_EXT:
            encoding, sep = _csv_params(p)
            df = pd.read_csv(p, sep=sep, encoding=encoding, dtype=str, nrows=nrows)
        else:
            engine = "xlrd" if ext == ".xls" else "openpyxl"
            df = pd.read_excel(p, sheet_name=sheet or 0, dtype=object, nrows=nrows, engine=engine)
    except ImportError as exc:
        raise ToolkitError(
            "Falta uma biblioteca para ler este formato (para .xls instale 'xlrd')."
        ) from exc
    df.columns = [str(c).strip() for c in df.columns]
    return df


def list_columns(path, sheet: str | None = None) -> list[str]:
    return list(read_table(path, sheet=sheet, nrows=0).columns)


def list_sheets(path) -> list[str]:
    p = Path(path)
    if p.suffix.lower() in _TEXT_EXT:
        return []
    engine = "xlrd" if p.suffix.lower() == ".xls" else "openpyxl"
    return list(pd.ExcelFile(p, engine=engine).sheet_names)
