"""Registro de módulos disponíveis e planejados."""
from __future__ import annotations

from core.base_module import BaseModule
from core.categories import CATEGORY_ORDER
from modules import available_modules
from modules.catalog import PLANNED, PlannedModule


class ModuleRegistry:
    def __init__(self):
        self._modules: dict[str, BaseModule] = {}
        self._planned: dict[str, PlannedModule] = {}

    def register(self, module: BaseModule) -> None:
        if module.module_id in self._modules or module.module_id in self._planned:
            raise ValueError(f"Módulo duplicado: {module.module_id}")
        self._modules[module.module_id] = module

    def register_planned(self, planned: PlannedModule) -> None:
        if planned.module_id in self._modules or planned.module_id in self._planned:
            raise ValueError(f"Módulo duplicado: {planned.module_id}")
        self._planned[planned.module_id] = planned

    def get(self, module_id: str) -> BaseModule | None:
        return self._modules.get(module_id)

    def get_planned(self, module_id: str) -> PlannedModule | None:
        return self._planned.get(module_id)

    def modules(self) -> list[BaseModule]:
        return list(self._modules.values())

    def planned(self) -> list[PlannedModule]:
        return list(self._planned.values())

    def categories(self) -> list[str]:
        return list(CATEGORY_ORDER)

    def name_of(self, module_id: str) -> str:
        item = self._modules.get(module_id) or self._planned.get(module_id)
        return item.name if item else module_id


def build_registry() -> ModuleRegistry:
    registry = ModuleRegistry()
    for module in available_modules():
        registry.register(module)
    for planned in PLANNED:
        registry.register_planned(planned)
    return registry
