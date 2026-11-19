"""Funções puras de normalização (texto, CNPJ, números e datas)."""
from __future__ import annotations

import numbers
import re
import unicodedata
from datetime import date, datetime, timedelta

import pandas as pd

_INVISIBLE = {ord(c): None for c in "\u200b\u200c\u200d\u2060\ufeff\u00ad"}
_SPACES = {ord(c): " " for c in "\u00a0\u2007\u202f\u2009\u3000"}
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def is_blank(value) -> bool:
    """True para None, NaN/NaT/NA e textos vazios ou só com espaços."""
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def clean_text(value):
    """Remove caracteres invisíveis, troca espaços especiais e colapsa espaços."""
    if not isinstance(value, str):
        return value
    text = value.translate(_INVISIBLE).translate(_SPACES)
    text = _CONTROL.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


def as_text(value) -> str:
    """Representação textual estável de qualquer valor de célula."""
    if is_blank(value):
        return ""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, datetime):
        if (value.hour, value.minute, value.second) == (0, 0, 0):
            return value.strftime("%Y-%m-%d")
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else repr(value)
    return clean_text(str(value))


# ---- CNPJ (numérico e alfanumérico) ---------------------------------------

def normalize_cnpj(value) -> str | None:
    """Devolve 14 caracteres [A-Z0-9] ou None se não for reconhecível.

    CNPJs numéricos que perderam zeros à esquerda (comum no Excel) são
    completados. Aceita o formato alfanumérico adotado pela Receita Federal.
    """
    text = as_text(value).upper()
    if not text:
        return None
    m = re.fullmatch(r"(\d+)\.0+", text)  # "12345678000190.0"
    if m:
        text = m.group(1)
    chars = re.sub(r"[^A-Z0-9]", "", text)
    if not chars or len(chars) > 14:
        return None
    if chars.isdigit():
        return chars.zfill(14)
    return chars if len(chars) == 14 else None


def format_cnpj(cnpj14: str) -> str:
    c = cnpj14
    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}"


def cnpj_is_valid(cnpj14: str) -> bool:
    """Valida os dois dígitos verificadores (módulo 11; letras valem ord(c) - 48)."""
    c = (cnpj14 or "").upper()
    if len(c) != 14 or not re.fullmatch(r"[A-Z0-9]{12}\d{2}", c) or c == c[0] * 14:
        return False

    def check_digit(base: str, weights: list[int]) -> str:
        total = sum((ord(ch) - 48) * w for ch, w in zip(base, weights))
        rest = total % 11
        return "0" if rest < 2 else str(11 - rest)

    w1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    d1 = check_digit(c[:12], w1)
    d2 = check_digit(c[:12] + d1, [6] + w1)
    return c[12:] == d1 + d2


# ---- números e datas ----------------------------------------------------------

def parse_number(value, fmt: str = "br") -> float | None:
    """Converte para float. fmt: "br" (1.234,56) ou "intl" (1,234.56).

    Números já numéricos passam direto. Aceita R$, parênteses e sinal no fim
    como negativo. Devolve None se não reconhecer.
    """
    if is_blank(value) or isinstance(value, bool):
        return None
    if isinstance(value, numbers.Real):
        return float(value)
    text = re.sub(r"(?i)r\$|\$|\s", "", as_text(value))
    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative, text = True, text[1:-1]
    if text.endswith("-"):
        negative, text = True, text[:-1]
    if text.startswith("-"):
        negative, text = True, text[1:]
    elif text.startswith("+"):
        text = text[1:]
    text = text.replace(".", "").replace(",", ".") if fmt == "br" else text.replace(",", "")
    if not re.fullmatch(r"\d+(\.\d+)?|\.\d+", text):
        return None
    number = float(text)
    return -number if negative else number


def _excel_serial(x: float) -> date | None:
    if 20000 <= x <= 80000:
        return (datetime(1899, 12, 30) + timedelta(days=x)).date()
    return None


_DATE_FORMATS = (
    "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y-%m-%d", "%Y/%m/%d", "%d/%m/%y",
    "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%Y-%m-%d %H:%M:%S",
)


def parse_date(value) -> date | None:
    """Converte para date. Aceita datas do Excel, dd/mm/aaaa, aaaa-mm-dd e serial do Excel."""
    if is_blank(value) or isinstance(value, bool):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, numbers.Real):
        return _excel_serial(float(value))
    text = as_text(value)
    if re.fullmatch(r"\d{5}(\.\d+)?", text):
        return _excel_serial(float(text))
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None
