"""Registro de módulos disponíveis e planejados."""
from __future__ import annotations

from core.base_module import PARAM_KINDS, BaseModule
from core.categories import CATEGORY_ORDER
from modules import available_modules
from modules.catalog import PLANNED, PlannedModule


def _validate_module(module: BaseModule) -> None:
    """Rejeita metadados inválidos antes de o módulo chegar à interface."""
    module_id = str(getattr(module, "module_id", "") or "").strip()
    if not module_id:
        raise ValueError(f"Módulo sem 'module_id': {type(module).__name__}.")
    if not str(getattr(module, "name", "") or "").strip():
        raise ValueError(f"Módulo '{module_id}' sem nome.")
    category = getattr(module, "category", "")
    if category not in CATEGORY_ORDER:
        raise ValueError(f"Módulo '{module_id}' tem categoria inválida: {category!r}.")

    params = list(getattr(module, "params", []) or [])
    keys = [str(getattr(spec, "key", "") or "") for spec in params]
    if any(not key for key in keys):
        raise ValueError(f"Módulo '{module_id}' tem parâmetro sem chave.")
    duplicates = sorted({key for key in keys if keys.count(key) > 1})
    if duplicates:
        raise ValueError(
            f"Módulo '{module_id}' tem chaves de parâmetro duplicadas: {', '.join(duplicates)}."
        )
    by_key = dict(zip(keys, params))

    for spec in params:
        kind = getattr(spec, "kind", None)
        if kind not in PARAM_KINDS:
            raise ValueError(
                f"Módulo '{module_id}', parâmetro '{spec.key}': tipo desconhecido {kind!r}. "
                f"Tipos válidos: {', '.join(PARAM_KINDS)}."
            )
        if kind == "choice":
            choices = list(getattr(spec, "choices", None) or [])
            if not choices:
                raise ValueError(
                    f"Módulo '{module_id}', parâmetro '{spec.key}': lista de opções (choices) vazia."
                )
            if spec.default is not None and spec.default not in choices:
                raise ValueError(
                    f"Módulo '{module_id}', parâmetro '{spec.key}': valor padrão "
                    f"{spec.default!r} não está nas opções."
                )
        if kind in ("column", "columns"):
            source = getattr(spec, "source", None)
            if not source:
                raise ValueError(
                    f"Módulo '{module_id}', parâmetro '{spec.key}': não informa 'source'."
                )
            if source not in by_key:
                raise ValueError(
                    f"Módulo '{module_id}', parâmetro '{spec.key}': 'source' aponta para "
                    f"parâmetro inexistente: {source!r}."
                )
            source_kind = by_key[source].kind
            if source_kind != "file":
                raise ValueError(
                    f"Módulo '{module_id}', parâmetro '{spec.key}': 'source' deve apontar para "
                    f"um parâmetro de arquivo, não para {source_kind!r}."
                )


class ModuleRegistry:
    def __init__(self):
        self._modules: dict[str, BaseModule] = {}
        self._planned: dict[str, PlannedModule] = {}

    def register(self, module: BaseModule) -> None:
        if module.module_id in self._modules or module.module_id in self._planned:
            raise ValueError(f"Módulo duplicado: {module.module_id}")
        _validate_module(module)
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
