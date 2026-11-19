"""Log em arquivo (rotativo). Não registre conteúdo financeiro nas mensagens."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from .paths import logs_dir

LOGGER_NAME = "finance_toolkit"
_configured = False


def setup_logging() -> logging.Logger:
    global _configured
    logger = logging.getLogger(LOGGER_NAME)
    if not _configured:
        logger.setLevel(logging.INFO)
        try:
            handler = RotatingFileHandler(
                logs_dir() / "finance_toolkit.log",
                maxBytes=1_000_000, backupCount=5, encoding="utf-8",
            )
            handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
            logger.addHandler(handler)
        except OSError:
            logger.addHandler(logging.NullHandler())
        _configured = True
    return logger


def get_logger() -> logging.Logger:
    return logging.getLogger(LOGGER_NAME)
