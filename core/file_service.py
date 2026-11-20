"""Operações seguras de arquivos: nomes, movimentação sem sobrescrita, hash, varredura."""
from __future__ import annotations

import hashlib
import os
import re
import shutil
from collections.abc import Iterable, Iterator
from pathlib import Path

RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def sanitize_folder_name(name: str) -> str:
    """Nome válido de pasta no Windows (sem caracteres proibidos, ponto/espaço final ou nome reservado)."""
    clean = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", str(name or ""))
    clean = re.sub(r"\s+", " ", clean).strip(" .")
    if clean.upper() in RESERVED_NAMES:
        clean += "_"
    return clean


def unique_path(path) -> Path:
    """Se o caminho já existe, acrescenta _1, _2... antes da extensão."""
    p = Path(path)
    if not p.exists():
        return p
    i = 1
    while True:
        candidate = p.with_name(f"{p.stem}_{i}{p.suffix}")
        if not candidate.exists():
            return candidate
        i += 1


def move_to(src, target) -> Path:
    """Move para um destino já planejado, sem nunca sobrescrever."""
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise FileExistsError(f"Destino já existe: {target}")
    shutil.move(str(src), str(target))
    return target


def move_safe(src, dest_folder) -> Path:
    """Move o arquivo para a pasta (criando-a) sem nunca sobrescrever."""
    dest_folder = Path(dest_folder)
    dest_folder.mkdir(parents=True, exist_ok=True)
    target = unique_path(dest_folder / Path(src).name)
    return move_to(src, target)


def hash_file(path, algorithm: str = "sha256", chunk: int = 1024 * 1024) -> str:
    h = hashlib.new(algorithm)
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def is_inside(path, parent) -> bool:
    try:
        Path(path).resolve().relative_to(Path(parent).resolve())
        return True
    except ValueError:
        return False


def iter_files(folder, recursive: bool = True, exclude: Iterable = ()) -> Iterator[Path]:
    """Lista arquivos; pastas em `exclude` são podadas da varredura inteira."""
    root = Path(folder)
    excluded = [Path(e).resolve() for e in exclude]
    if not recursive:
        for p in sorted(root.iterdir()):
            if p.is_file():
                yield p
        return
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if Path(dirpath, d).resolve() not in excluded]
        for name in filenames:
            yield Path(dirpath, name)


def resolve_output_dir(chosen: str | None, fallback_file) -> Path:
    """Pasta de saída escolhida, ou a pasta do arquivo de origem."""
    if chosen:
        out = Path(chosen)
        out.mkdir(parents=True, exist_ok=True)
        return out
    return Path(fallback_file).resolve().parent
