"""Criador de pastas por empresa.

Lê a coluna de razão social e a de situação cadastral de uma planilha e cria,
na pasta escolhida, uma pasta com o NOME CURTO de cada empresa ATIVA.
Ex.: "BB EMPREENDIMENTOS E PARTICIPACOES SA" -> "BB".
"""
from __future__ import annotations

import re
from pathlib import Path

from core.base_module import BaseModule, Issue, ParamSpec, Result, build_result
from core.categories import CATEGORY_FILES
from core.exceptions import CancelledError, ValidationError
from core.file_service import sanitize_folder_name
from core.normalizers import as_text, is_blank, strip_accents
from core.spreadsheet_service import SHEET_FILETYPES, read_table

DEFAULT_CUT_WORDS = (
    "SA, LTDA, EIRELI, ME, EPP, MEI, SS, CIA, EMPREENDIMENTO, EMPREENDIMENTOS, PARTICIPACAO, "
    "PARTICIPACOES, HOLDING, COMERCIO, INDUSTRIA, SERVICOS, INCORPORACAO, INCORPORACOES, "
    "ADMINISTRACAO, ADMINISTRADORA, INVESTIMENTOS, IMOBILIARIA, IMOBILIARIOS, CONSTRUCAO, "
    "CONSTRUTORA, EMPRESA, GRUPO"
)
NO_COMPANY = "SEM_EMPRESA"


def _token(word: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", strip_accents(word).upper())


def parse_word_list(text: str | None) -> set[str]:
    """Lista separada por vírgula, ponto e vírgula ou quebra de linha, normalizada."""
    return {t for t in (_token(w) for w in re.split(r"[,;\n]", text or "")) if t}


def short_company_name(value, cut_words: set[str]) -> str:
    """Mantém o nome até a primeira palavra de corte (a primeira palavra nunca é cortada).

    "BB EMPREENDIMENTOS E PARTICIPACOES SA" -> "BB"
    "Banco do Brasil S.A."                  -> "BANCO DO BRASIL"
    """
    if is_blank(value):
        return NO_COMPANY
    text = re.sub(r"\s+", " ", strip_accents(as_text(value)).upper()).strip()
    words = text.split(" ")
    kept = [words[0]]
    for word in words[1:]:
        if _token(word) in cut_words:
            break
        kept.append(word)
    return sanitize_folder_name(" ".join(kept)) or NO_COMPANY


class CompanyFolders(BaseModule):
    module_id = "company_folders"
    name = "Criador de pastas por empresa"
    category = CATEGORY_FILES
    description = (
        "Cria uma pasta para cada empresa com situação cadastral ATIVA, usando só o nome curto "
        "(ex.: “BB EMPREENDIMENTOS E PARTICIPACOES SA” vira “BB”). Pastas já existentes não são alteradas."
    )
    modifies_files = True
    params = [
        ParamSpec("spreadsheet", "Planilha de empresas", "file", filetypes=SHEET_FILETYPES),
        ParamSpec("sheet", "Aba (vazio = primeira)", "text", required=False),
        ParamSpec("name_column", "Coluna do nome (ex.: Razão Social)", "column", default="Razão Social", source="spreadsheet"),
        ParamSpec("status_column", "Coluna da situação (ex.: Situação Cadastral)", "column",
                  default="Situação Cadastral", source="spreadsheet"),
        ParamSpec("active_values", "Valores que contam como ativos", "text", default="ATIVA, ATIVO"),
        ParamSpec("target_folder", "Pasta onde criar as subpastas", "folder"),
        ParamSpec("cut_words", "Palavras de corte do nome", "multiline", default=DEFAULT_CUT_WORDS,
                  required=False, height=4,
                  help="O nome é cortado na primeira dessas palavras (exceto se for a primeira do nome)."),
    ]

    def validate(self, inputs: dict) -> list[Issue]:
        issues = super().validate(inputs)
        if inputs.get("name_column") and inputs.get("name_column") == inputs.get("status_column"):
            issues.append(Issue.error("A coluna do nome e a da situação devem ser diferentes."))
        return issues

    def _plan(self, inputs: dict, ctx):
        df = read_table(inputs["spreadsheet"], inputs.get("sheet") or None)
        for key in ("name_column", "status_column"):
            if inputs[key] not in df.columns:
                raise ValidationError(f"Coluna '{inputs[key]}' não encontrada na planilha.")
        active = parse_word_list(inputs.get("active_values"))
        if not active:
            raise ValidationError("Informe ao menos um valor de situação considerado ativo.")
        cut_words = parse_word_list(inputs.get("cut_words"))

        names, statuses = df[inputs["name_column"]].tolist(), df[inputs["status_column"]].tolist()
        total = len(names)
        ctx.log(f"{total} linha(s) lidas da planilha.")
        seen: dict[str, str] = {}
        inactive = unnamed = repeated = 0
        for i, (raw, status) in enumerate(zip(names, statuses), start=1):
            ctx.check_cancel()
            ctx.progress(i, total, "Lendo linhas")
            if _token(as_text(status)) not in active:
                inactive += 1
            elif is_blank(raw):
                unnamed += 1
            else:
                folder = short_company_name(raw, cut_words)
                if folder in seen:
                    repeated += 1
                else:
                    seen[folder] = as_text(raw)
        return seen, inactive, unnamed, repeated

    def preview(self, inputs: dict, ctx) -> Result:
        seen, inactive, unnamed, repeated = self._plan(inputs, ctx)
        target = Path(inputs["target_folder"])
        rows, will_create = [], 0
        for folder, original in seen.items():
            exists = (target / folder).is_dir()
            will_create += 0 if exists else 1
            rows.append({"Pasta": folder, "Nome original": original,
                         "Situação da pasta": "Já existe" if exists else "Será criada"})
        return build_result(
            f"{will_create} pasta(s) seriam criadas e {len(seen) - will_create} já existem; "
            f"{inactive} linha(s) ignoradas (situação diferente de ativa), {repeated} nome(s) repetido(s).",
            processed=len(seen), warnings=unnamed, details=rows,
        )

    def execute(self, inputs: dict, ctx) -> Result:
        seen, inactive, unnamed, repeated = self._plan(inputs, ctx)
        target = Path(inputs["target_folder"])
        rows, created, existing, errors, cancelled = [], 0, 0, 0, False
        items = list(seen.items())
        for i, (folder, original) in enumerate(items, start=1):
            try:
                ctx.check_cancel()
                ctx.progress(i, len(items), "Criando pastas")
                path = target / folder
                if path.is_dir():
                    existing += 1
                    outcome = "Já existia"
                else:
                    path.mkdir(parents=True)
                    created += 1
                    outcome = "Criada"
                rows.append({"Pasta": folder, "Nome original": original, "Resultado": outcome})
            except CancelledError:
                cancelled = True
                break
            except OSError as exc:
                errors += 1
                ctx.log(f"Erro ao criar '{folder}': {exc}", "error")
                rows.append({"Pasta": folder, "Nome original": original, "Resultado": f"Erro: {exc}"})
        ctx.log(f"{created} criada(s), {existing} já existia(m), {errors} erro(s).")
        result = build_result(
            f"{created} pasta(s) criada(s), {existing} já existia(m), {errors} erro(s). "
            f"{inactive} linha(s) ignoradas por situação, {repeated} nome(s) repetido(s) agrupados.",
            processed=created + existing, warnings=unnamed, errors=errors, details=rows,
        )
        if cancelled:
            result.status = "cancelled"
        return result
