"""Configurações: últimos parâmetros de cada módulo e preferências do app."""
from __future__ import annotations

from .history_service import HistoryService

_APP = "_app"


class ConfigService:
    def __init__(self, history: HistoryService):
        self._history = history

    def module_inputs(self, module_id: str) -> dict:
        return self._history.get_settings(module_id)

    def save_module_inputs(self, module_id: str, inputs: dict) -> None:
        self._history.set_settings(module_id, inputs)

    def app_setting(self, key: str, default=None):
        return self._history.get_settings(_APP).get(key, default)

    def set_app_setting(self, key: str, value) -> None:
        data = self._history.get_settings(_APP)
        data[key] = value
        self._history.set_settings(_APP, data)
