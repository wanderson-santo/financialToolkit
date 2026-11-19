"""Exceções do Finance Toolkit."""


class ToolkitError(Exception):
    """Erro esperado, com mensagem pronta para o usuário."""


class ValidationError(ToolkitError):
    """Parâmetros ou dados de entrada inválidos."""


class CancelledError(ToolkitError):
    """Execução cancelada pelo usuário."""
