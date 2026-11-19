"""Locais de dados do aplicativo (banco, logs, backups)."""
from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "FinanceToolkit"


def app_data_dir() -> Path:
    """Pasta de dados do usuário. Pode ser sobrescrita por FINANCE_TOOLKIT_HOME (testes)."""
    override = os.environ.get("FINANCE_TOOLKIT_HOME")
    if override:
        base = Path(override)
    elif os.name == "nt":
        base = Path(os.environ.get("APPDATA") or Path.home()) / APP_NAME
    else:
        base = Path.home() / ".finance_toolkit"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _sub(name: str) -> Path:
    p = app_data_dir() / name
    p.mkdir(parents=True, exist_ok=True)
    return p


def logs_dir() -> Path:
    return _sub("logs")


def backups_dir() -> Path:
    return _sub("backups")


def db_path() -> Path:
    return app_data_dir() / "finance_toolkit.db"
