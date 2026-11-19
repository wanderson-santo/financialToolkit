"""Inicialização: logs, serviços, registro de módulos e janela principal."""
from __future__ import annotations

import sys

from app.module_registry import build_registry
from app.services import Services
from core.config_service import ConfigService
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


def run() -> None:
    logger = setup_logging()
    logger.info("Finance Toolkit iniciando")
    _enable_hidpi()
    from app.main_window import MainWindow  # importa o Tkinter só aqui

    history = HistoryService(db_path())
    services = Services(history=history, config=ConfigService(history))
    MainWindow(services, build_registry()).mainloop()
