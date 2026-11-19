"""Inicialização: logs, serviços, registro de módulos e janela principal."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

from app.module_registry import build_registry
from app.services import Services
from core.config_service import ConfigService
from core.exceptions import ToolkitError
from core.history_service import HistoryService
from core.logging_service import setup_logging
from core.paths import db_path


def _enable_hidpi() -> None:
    if sys.platform.startswith("win"):
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:  # noqa: BLE001 - recurso opcional
            pass


def _show_message(title: str, message: str, warning: bool = False) -> None:
    """Mostra um diálogo nativo mesmo antes da janela principal existir."""
    if sys.platform.startswith("win"):
        try:
            import ctypes
            flags = 0x30 if warning else 0x10  # ícone de aviso/erro
            ctypes.windll.user32.MessageBoxW(0, message, title, flags)
            return
        except Exception:  # noqa: BLE001 - tenta o Tkinter como alternativa
            pass
    try:
        from tkinter import messagebox
        (messagebox.showwarning if warning else messagebox.showerror)(title, message)
    except Exception:  # noqa: BLE001 - último recurso quando não há interface
        print(f"{title}: {message}", file=sys.stderr)


def _recovery_notice(backup: Path, error: Exception) -> None:
    _show_message(
        "Histórico recuperado",
        "O banco de dados do histórico estava corrompido e foi preservado em:\n"
        f"{backup}\n\n"
        "Um novo banco foi criado. As execuções anteriores não estarão disponíveis.",
        warning=True,
    )


def _startup_error_message(exc: Exception) -> str:
    if isinstance(exc, ToolkitError):
        return str(exc)
    if isinstance(exc, OSError):
        return (
            "Não foi possível acessar a pasta de dados do aplicativo.\n\n"
            f"{exc}\n\n"
            "Verifique as permissões da pasta e tente novamente."
        )
    if isinstance(exc, sqlite3.DatabaseError):
        return (
            "Não foi possível abrir o banco de dados do histórico.\n\n"
            f"{exc}\n\n"
            "Feche outras instâncias do aplicativo, verifique as permissões da pasta "
            "e tente novamente."
        )
    return f"O aplicativo não pôde iniciar.\n\n{exc}"


def run() -> None:
    logger = None
    try:
        logger = setup_logging()
        logger.info("Finance Toolkit iniciando")
        _enable_hidpi()
        history = HistoryService.open_with_recovery(db_path(), on_recover=_recovery_notice)
        services = Services(history=history, config=ConfigService(history))
        from app.main_window import MainWindow  # importa o Tkinter só aqui
        MainWindow(services, build_registry()).mainloop()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 - garante aviso ao usuário no executável
        if logger is not None:
            logger.exception("Falha na inicialização")
        _show_message("Finance Toolkit", _startup_error_message(exc))
        raise SystemExit(1) from exc
