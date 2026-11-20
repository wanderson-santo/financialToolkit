"""Serviços compartilhados entregues às páginas."""
from __future__ import annotations

from dataclasses import dataclass, field

from core.config_service import ConfigService
from core.history_service import HistoryService
from core.operation_coordinator import OperationCoordinator


@dataclass
class Services:
    history: HistoryService
    config: ConfigService
    coordinator: OperationCoordinator = field(default_factory=OperationCoordinator)
