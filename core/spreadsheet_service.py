"""Leitura de planilhas (XLSX, XLSM, XLS e CSV) com detecção de codificação e separador."""
from __future__ import annotations

import codecs
import csv
import io
import re
from pathlib import Path

import pandas as pd

from .exceptions import ToolkitError
from .logging_service import get_logger

SHEET_FILETYPES = [("Planilhas", "*.xlsx *.xlsm *.xls *.csv *.tsv *.txt"), ("Todos os arquivos", "*.*")]
_TEXT_EXT = {".csv", ".txt", ".tsv"}
_UNNAMED_HEADER = re.compile(r"^Unnamed: \d+$")
_ENCODINGS = ("utf-8-sig", "cp1252", "latin-1")
_DELIMITERS = (";", ",", "\t", "|")
_SAMPLE_SIZE = 65536


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


def _can_decode(path: Path, encoding: str) -> bool:
    """Valida a codificação no arquivo inteiro, em blocos."""
    decoder = codecs.getincrementaldecoder(encoding)()
    try:
        with path.open("rb") as fh:
            while chunk := fh.read(1 << 20):
                decoder.decode(chunk)
        decoder.decode(b"", final=True)
    except UnicodeDecodeError:
        return False
    return True


def _detect_encoding(path: Path, encoding: str | None) -> str:
    if encoding:
        try:
            codecs.lookup(encoding)
        except LookupError as exc:
            raise ToolkitError(f"Codificação desconhecida: {encoding!r}.") from exc
        if _can_decode(path, encoding):
            return encoding
        raise ToolkitError(
            f"Não foi possível decodificar {path.name} com a codificação '{encoding}'. "
            "Tente UTF-8, cp1252 (Windows-1252) ou latin-1."
        )
    for enc in _ENCODINGS:
        if _can_decode(path, enc):
            return enc
    return "latin-1"  # inalcançável: latin-1 aceita qualquer byte


def _sample_text(path: Path, encoding: str) -> str:
    decoder = codecs.getincrementaldecoder(encoding)()
    with path.open("rb") as fh:
        raw = fh.read(_SAMPLE_SIZE)
    return decoder.decode(raw, final=False)


def _detect_separator(sample: str) -> str:
    """Escolhe o separador pela consistência das colunas, respeitando aspas."""
    best, best_score = ";", None
    for sep in _DELIMITERS:
        try:
            rows = [
                row for row in csv.reader(io.StringIO(sample), delimiter=sep)
                if any(cell.strip() for cell in row)
            ]
        except csv.Error:
            continue
        widths = [len(row) for row in rows]
        if not widths:
            continue
        mode = max(widths, key=lambda w: (widths.count(w), w))
        score = (mode > 1, widths.count(mode) / len(widths), mode)
        if best_score is None or score > best_score:
            best, best_score = sep, score
    return best


def _csv_params(
    path: Path, encoding: str | None = None, separator: str | None = None
) -> tuple[str, str]:
    if separator is not None and len(separator) != 1:
        raise ToolkitError("O separador do CSV deve ter exatamente um caractere.")
    enc = _detect_encoding(path, encoding)
    sep = separator or _detect_separator(_sample_text(path, enc))
    get_logger().info(
        "CSV %s: codificação %s, separador %r%s.",
        path.name, enc, sep, " (forçado)" if separator else "",
    )
    return enc, sep


def read_table(
    path,
    sheet: str | None = None,
    nrows: int | None = None,
    encoding: str | None = None,
    separator: str | None = None,
) -> pd.DataFrame:
    """Lê a planilha preservando tipos nativos do Excel (dtype=object).

    CSV é lido todo como texto. A codificação é validada no arquivo inteiro
    (utf-8-sig, cp1252 e latin-1, nessa ordem) e o separador é detectado
    respeitando aspas; ``encoding`` e ``separator`` permitem forçar uma
    escolha. Os nomes das colunas viram `str`, recebem ``strip`` e são
    tornados únicos por :func:`unique_headers`; renomeações são registradas
    no log.
    """
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {p}")
    ext = p.suffix.lower()
    try:
        if ext in _TEXT_EXT:
            enc, sep = _csv_params(p, encoding, separator)
            try:
                df = pd.read_csv(p, sep=sep, encoding=enc, dtype=str, nrows=nrows)
            except UnicodeDecodeError as exc:
                raise ToolkitError(
                    f"Não foi possível decodificar {p.name} como texto ({enc}). "
                    "Verifique a codificação do arquivo ou selecione outra."
                ) from exc
            except pd.errors.EmptyDataError as exc:
                raise ToolkitError(
                    f"O arquivo {p.name} está vazio ou não possui cabeçalho."
                ) from exc
            except pd.errors.ParserError as exc:
                raise ToolkitError(
                    f"Não foi possível interpretar {p.name} como CSV: {exc}"
                ) from exc
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


def list_columns(path, sheet: str | None = None, encoding: str | None = None,
                 separator: str | None = None) -> list[str]:
    return list(read_table(
        path, sheet=sheet, nrows=0, encoding=encoding, separator=separator,
    ).columns)


def list_sheets(path) -> list[str]:
    p = Path(path)
    if p.suffix.lower() in _TEXT_EXT:
        return []
    engine = "xlrd" if p.suffix.lower() == ".xls" else "openpyxl"
    return list(pd.ExcelFile(p, engine=engine).sheet_names)
