"""Validações reutilizáveis pelos módulos."""
from __future__ import annotations

from .normalizers import cnpj_is_valid, is_blank, normalize_cnpj


def validate_cnpj(value) -> tuple[bool, str, str | None]:
    """Devolve (válido, motivo, cnpj_normalizado)."""
    if is_blank(value):
        return False, "Vazio", None
    cnpj = normalize_cnpj(value)
    if cnpj is None:
        return False, "Formato/tamanho inválido", None
    if not cnpj_is_valid(cnpj):
        return False, "Dígitos verificadores inválidos", cnpj
    return True, "Válido", cnpj


def find_duplicates(keys: list[str]) -> dict[str, list[int]]:
    """Mapa chave -> posições (0-based) das chaves que aparecem mais de uma vez."""
    seen: dict[str, list[int]] = {}
    for i, key in enumerate(keys):
        if key:
            seen.setdefault(key, []).append(i)
    return {k: v for k, v in seen.items() if len(v) > 1}
