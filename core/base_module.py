"""Contrato comum de todos os utilitários.

Cada módulo declara seus parâmetros (ParamSpec) e implementa `preview` e
`execute`. A interface monta o formulário automaticamente a partir dos
parâmetros, então um módulo novo não exige mexer na tela.
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

RUNNING = "running"
SUCCESS = "success"
PARTIAL = "partial_success"
FAILED = "failed"
CANCELLED = "cancelled"
INTERRUPTED = "interrupted"

STATUS_LABELS = {
    SUCCESS: "Concluído",
    PARTIAL: "Concluído com erros",
    FAILED: "Falhou",
    CANCELLED: "Cancelado",
    RUNNING: "Em andamento",
    INTERRUPTED: "Interrompido",
}

RESULT_STATUSES = frozenset({SUCCESS, PARTIAL, FAILED, CANCELLED, INTERRUPTED})


def validate_status(status: str) -> str:
    """Garante que o status é um resultado conhecido; devolve o próprio status."""
    if status not in RESULT_STATUSES:
        raise ValueError(f"Status de resultado inválido: {status!r}")
    return status


PARAM_KINDS = ("file", "folder", "text", "multiline", "choice", "bool", "column", "columns")


@dataclass
class ParamSpec:
    """Descreve um campo do formulário de um módulo.

    ``kind`` deve ser um de ``PARAM_KINDS``.

    kind:
      file     - seleção de arquivo
      folder   - seleção de pasta
      text     - texto de uma linha
      multiline- texto de várias linhas
      choice   - lista fechada (`choices`)
      bool     - caixa de marcação
      column   - uma coluna da planilha escolhida em `source`
      columns  - várias colunas da planilha escolhida em `source`

    Para column/columns, `default` funciona como dica de nome: a coluna cujo
    nome for igual (ou contiver o texto) é selecionada automaticamente.
    """

    key: str
    label: str
    kind: str
    default: Any = None
    required: bool = True
    choices: list[str] | None = None
    source: str | None = None
    help: str = ""
    filetypes: list[tuple[str, str]] | None = None
    height: int = 4


@dataclass
class Issue:
    level: str  # "error" | "warning"
    message: str

    @staticmethod
    def error(message: str) -> "Issue":
        return Issue("error", message)

    @staticmethod
    def warning(message: str) -> "Issue":
        return Issue("warning", message)


@dataclass
class Result:
    """Resultado de uma execução. `status` deve ser um de ``RESULT_STATUSES``."""

    status: str = SUCCESS
    summary: str = ""
    processed: int = 0
    warnings: int = 0
    errors: int = 0
    output_files: list[str] = field(default_factory=list)
    details: list[dict] = field(default_factory=list)
    is_preview: bool = False

    def __post_init__(self) -> None:
        validate_status(self.status)


def build_result(
    summary: str,
    processed: int,
    warnings: int = 0,
    errors: int = 0,
    output_files: list[str] | None = None,
    details: list[dict] | None = None,
    status: str | None = None,
) -> Result:
    """Monta o Result. Um `status` explícito tem prioridade sobre os contadores."""
    if status is None:
        if errors == 0:
            status = SUCCESS
        elif processed > 0:
            status = PARTIAL
        else:
            status = FAILED
    return Result(
        status=status,
        summary=summary,
        processed=processed,
        warnings=warnings,
        errors=errors,
        output_files=output_files or [],
        details=details or [],
    )


class BaseModule(ABC):
    module_id: str = ""
    name: str = ""
    category: str = ""
    description: str = ""
    version: str = "1.0.0"
    params: list[ParamSpec] = []
    modifies_files: bool = False

    def requires_confirmation(self, inputs: dict) -> bool:
        """Se True, a interface pede confirmação antes de executar."""
        return self.modifies_files

    def validate(self, inputs: dict) -> list[Issue]:
        """Validação genérica (obrigatórios e existência). Módulos podem estender."""
        issues: list[Issue] = []
        for spec in self.params:
            if spec.kind == "bool":
                continue
            value = inputs.get(spec.key)
            if value in (None, "", []):
                if spec.required:
                    issues.append(Issue.error(f"Preencha: {spec.label}."))
                continue
            if spec.kind == "file" and not os.path.isfile(str(value)):
                issues.append(Issue.error(f"Arquivo não encontrado: {value}"))
            elif spec.kind == "folder" and not os.path.isdir(str(value)):
                issues.append(Issue.error(f"Pasta não encontrada: {value}"))
        return issues

    @abstractmethod
    def preview(self, inputs: dict, ctx) -> Result:
        """Mostra o que seria feito, sem alterar nenhum arquivo."""

    @abstractmethod
    def execute(self, inputs: dict, ctx) -> Result:
        """Executa o processamento e devolve um resultado estruturado."""
