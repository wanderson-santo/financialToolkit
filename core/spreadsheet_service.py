"""Leitura de planilhas (XLSX, XLSM, XLS e CSV) com detecção de codificação e separador."""
from __future__ import annotations

import codecs
import re
from pathlib import Path

import pandas as pd

from .exceptions import ToolkitError
from .logging_service import get_logger

SHEET_FILETYPES = [("Planilhas", "*.xlsx *.xlsm *.xls *.csv *.tsv *.txt"), ("Todos os arquivos", "*.*")]
_TEXT_EXT = {".csv", ".txt", ".tsv"}
_UNNAMED_HEADER = re.compile(r"^Unnamed: \d+$")


def _header_base(value) -> str:
    """Nome-base de um cabeçalho: sem espaços, nunca vazio."""
    text = "" if value is None else str(value).strip()
    if not text or _UNNAMED_HEADER.fullmatch(text):
        return "Coluna"
    return text


def unique_headers(columns) -> list[str]:
    """Torna os nomes de coluna únicos, preservando a ordem.

    Cabeçalhos vazios (ou gerados pelo pandas como ``Unnamed: N``) viram
    ``Coluna``. Repetições recebem sufixo ``_2``, ``_3`` etc. A busca evita
    colidir com nomes que já existam na planilha, então o resultado é
    determinístico e nenhuma coluna é descartada.
    """
    used: set[str] = set()
    names: list[str] = []
    for value in columns:
        base = _header_base(value)
        name, counter = base, 2
        while name in used:
            name = f"{base}_{counter}"
            counter += 1
        used.add(name)
        names.append(name)
    return names


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

    CSV é lido todo como texto. Os nomes das colunas viram `str`, recebem
    ``strip`` e são tornados únicos por :func:`unique_headers`; renomeações
    são registradas no log.
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
    original = list(df.columns)
    df.columns = unique_headers(original)
    changes = [(str(old), new) for old, new in zip(original, df.columns) if str(old) != new]
    if changes:
        shown = "; ".join(f"{old!r} -> {new!r}" for old, new in changes[:20])
        extra = f" (+{len(changes) - 20} outros)" if len(changes) > 20 else ""
        bases = [_header_base(col) for col in original]
        risky = len(set(bases)) < len(bases) or "Coluna" in bases
        logger = get_logger()
        log = logger.warning if risky else logger.info
        log("Cabeçalhos ajustados em %s: %s%s", p.name, shown, extra)
    return df


def list_columns(path, sheet: str | None = None) -> list[str]:
    return list(read_table(path, sheet=sheet, nrows=0).columns)


def list_sheets(path) -> list[str]:
    p = Path(path)
    if p.suffix.lower() in _TEXT_EXT:
        return []
    engine = "xlrd" if p.suffix.lower() == ".xls" else "openpyxl"
    return list(pd.ExcelFile(p, engine=engine).sheet_names)
