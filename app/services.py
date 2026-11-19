"""Serviços compartilhados entregues às páginas."""
from __future__ import annotations

from dataclasses import dataclass

from core.config_service import ConfigService
from core.history_service import HistoryService


@dataclass
class Services:
    history: HistoryService
    config: ConfigService
