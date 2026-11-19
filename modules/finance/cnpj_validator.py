"""Validador de CNPJ: dígitos verificadores, formatação e duplicidades."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from core.base_module import BaseModule, ParamSpec, Result, build_result
from core.categories import CATEGORY_FINANCE
from core.export_service import export_sheets
from core.file_service import resolve_output_dir, unique_path
from core.normalizers import format_cnpj
from core.spreadsheet_service import SHEET_FILETYPES, read_table
from core.validation_service import find_duplicates, validate_cnpj


class CnpjValidator(BaseModule):
    module_id = "cnpj_validator"
    name = "Validador de CNPJ"
    category = CATEGORY_FINANCE
    description = (
        "Valida os dígitos verificadores dos CNPJs de uma coluna (numéricos e alfanuméricos), padroniza o "
        "formato e aponta registros inválidos e duplicados. Gera uma cópia da planilha com 3 colunas novas."
    )
    params = [
        ParamSpec("spreadsheet", "Planilha de entrada", "file", filetypes=SHEET_FILETYPES),
        ParamSpec("sheet", "Aba (vazio = primeira)", "text", required=False),
        ParamSpec("column", "Coluna do CNPJ", "column", default="CNPJ", source="spreadsheet"),
        ParamSpec("output_folder", "Pasta de saída (vazio = mesma do original)", "folder", required=False),
    ]

    def _analyze(self, inputs: dict, ctx):
        df = read_table(inputs["spreadsheet"], inputs.get("sheet") or None)
        column = inputs["column"]
        values = df[column].tolist()
        total = len(values)
        ctx.log(f"{total} linha(s) lidas.")
        checked = []
        for i, v in enumerate(values, start=1):
            if i % 1000 == 0:
                ctx.check_cancel()
            ctx.progress(i, total, "Validando CNPJs")
            checked.append(validate_cnpj(v))
        dups = find_duplicates([c[2] if c[0] else "" for c in checked])
        return df, values, checked, dups

    @staticmethod
    def _rows(values, checked, dups):
        position: dict[int, str] = {}
        for positions in dups.values():
            lines = ", ".join(str(p + 2) for p in positions)  # linha no Excel = posição + 2
            for p in positions:
                position[p] = lines
        rows, invalid, duplicated = [], 0, 0
        for i, (raw, (ok, reason, cnpj)) in enumerate(zip(values, checked)):
            invalid += not ok
            duplicated += i in position
            rows.append({
                "Linha": i + 2,
                "CNPJ original": "" if raw is None or raw != raw else str(raw),
                "CNPJ formatado": format_cnpj(cnpj) if cnpj else "",
                "Situação": reason,
                "Duplicado nas linhas": position.get(i, ""),
            })
        return rows, invalid, duplicated

    def preview(self, inputs: dict, ctx) -> Result:
        _, values, checked, dups = self._analyze(inputs, ctx)
        rows, invalid, duplicated = self._rows(values, checked, dups)
        return build_result(
            f"Pré-visualização: {len(rows)} linha(s); {invalid} inválida(s)/vazia(s); "
            f"{duplicated} linha(s) em CNPJs duplicados ({len(dups)} CNPJ(s)).",
            processed=len(rows), warnings=invalid + duplicated, details=rows,
        )

    def execute(self, inputs: dict, ctx) -> Result:
        df, values, checked, dups = self._analyze(inputs, ctx)
        rows, invalid, duplicated = self._rows(values, checked, dups)
        out = df.copy()
        out["CNPJ_Formatado"] = [r["CNPJ formatado"] for r in rows]
        out["CNPJ_Situacao"] = [r["Situação"] for r in rows]
        out["CNPJ_Duplicado_Linhas"] = [r["Duplicado nas linhas"] for r in rows]
        src = Path(inputs["spreadsheet"])
        out_path = unique_path(resolve_output_dir(inputs.get("output_folder"), src) / f"{src.stem}_cnpj_validado.xlsx")
        export_sheets({"CNPJ validado": out}, out_path)
        ctx.log(f"Planilha gravada em {out_path}")
        return build_result(
            f"{len(rows)} linha(s) analisadas; {invalid} inválida(s)/vazia(s); {duplicated} linha(s) em "
            f"CNPJs duplicados. Gravado: {out_path.name}.",
            processed=len(rows), warnings=invalid + duplicated, output_files=[str(out_path)], details=rows,
        )
