"""Organizador automático de pastas.

Baseado nos scripts de organização por nome/extensão: classifica os arquivos
da raiz de uma pasta e os move para subpastas. Regras por nome têm prioridade
sobre as regras por extensão. Nunca sobrescreve (acrescenta _1, _2...).
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from core.base_module import BaseModule, Issue, ParamSpec, Result, build_result
from core.categories import CATEGORY_FILES
from core.exceptions import CancelledError, ValidationError
from core.file_service import move_safe, sanitize_folder_name

DEFAULT_EXT_RULES = (
    "Imagens=.jpg, .jpeg, .png, .gif\n"
    "Documentos=.pdf, .docx, .doc, .txt\n"
    "Excel=.xlsx, .xls, .xlsm, .csv\n"
    "Compactados=.zip, .rar, .7z"
)
IGNORED_NAMES = {"desktop.ini", "thumbs.db"}


def parse_rules(text: str | None) -> list[tuple[str, list[str]]]:
    """Lê linhas no formato `Pasta=termo1, termo2`. Linhas vazias e `#` são ignoradas."""
    rules: list[tuple[str, list[str]]] = []
    for number, raw in enumerate((text or "").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValidationError(f"Regra inválida na linha {number}: use o formato Pasta=termo1, termo2.")
        folder, terms = line.split("=", 1)
        folder = sanitize_folder_name(folder)
        items = [t.strip().lower() for t in terms.split(",") if t.strip()]
        if not folder or not items:
            raise ValidationError(f"Regra incompleta na linha {number}: informe a pasta e ao menos um termo.")
        rules.append((folder, items))
    return rules


class FolderOrganizer(BaseModule):
    module_id = "folder_organizer"
    name = "Organizador automático de pastas"
    category = CATEGORY_FILES
    description = (
        "Classifica os arquivos de uma pasta e os move para subpastas: primeiro por palavras-chave "
        "no nome (prioridade) e depois por extensão. Use a pré-visualização antes de executar; "
        "nada é sobrescrito."
    )
    modifies_files = True
    params = [
        ParamSpec("folder", "Pasta a organizar", "folder"),
        ParamSpec(
            "name_rules", "Regras por nome do arquivo (Pasta=termo1, termo2)", "multiline",
            default="Bradesco=bradesco", required=False, height=4,
            help="Uma regra por linha. Vale a primeira regra cujo termo aparece no nome (sem diferenciar maiúsculas).",
        ),
        ParamSpec("use_extensions", "Classificar também por extensão", "bool", default=True),
        ParamSpec(
            "ext_rules", "Regras por extensão (Pasta=.ext1, .ext2)", "multiline",
            default=DEFAULT_EXT_RULES, required=False, height=5,
        ),
        ParamSpec(
            "others_folder", "Pasta para arquivos não classificados", "text", default="Outros", required=False,
            help="Deixe vazio para manter os não classificados onde estão.",
        ),
    ]

    def validate(self, inputs: dict) -> list[Issue]:
        issues = super().validate(inputs)
        try:
            rules = parse_rules(inputs.get("name_rules"))
            if inputs.get("use_extensions"):
                rules += parse_rules(inputs.get("ext_rules"))
            if not rules and not (inputs.get("others_folder") or "").strip():
                issues.append(Issue.error("Defina ao menos uma regra ou a pasta para não classificados."))
        except ValidationError as exc:
            issues.append(Issue.error(str(exc)))
        return issues

    # ---- planejamento -------------------------------------------------------

    def _plan(self, inputs: dict, ctx) -> list[tuple[Path, str | None, str]]:
        folder = Path(inputs["folder"])
        name_rules = parse_rules(inputs.get("name_rules"))
        ext_rules: list[tuple[str, list[str]]] = []
        if inputs.get("use_extensions"):
            for fname, exts in parse_rules(inputs.get("ext_rules")):
                ext_rules.append((fname, [e if e.startswith(".") else "." + e for e in exts]))
        others = sanitize_folder_name(inputs.get("others_folder") or "")

        files = sorted(p for p in folder.iterdir()
                       if p.is_file() and p.name.lower() not in IGNORED_NAMES and not p.name.startswith("~$"))
        plan: list[tuple[Path, str | None, str]] = []
        for i, path in enumerate(files, start=1):
            ctx.check_cancel()
            ctx.progress(i, len(files), "Classificando arquivos")
            lower, ext = path.name.lower(), path.suffix.lower()
            dest, why = None, "sem regra aplicável"
            for fname, terms in name_rules:
                hit = next((t for t in terms if t in lower), None)
                if hit:
                    dest, why = fname, f"nome contém “{hit}”"
                    break
            if dest is None:
                for fname, exts in ext_rules:
                    if ext in exts:
                        dest, why = fname, f"extensão {ext}"
                        break
            if dest is None and others:
                dest, why = others, "não classificado"
            plan.append((path, dest, why))
        return plan

    @staticmethod
    def _rows(plan) -> list[dict]:
        return [{"Arquivo": p.name, "Destino": d or "(permanece)", "Motivo": why} for p, d, why in plan]

    def preview(self, inputs: dict, ctx) -> Result:
        plan = self._plan(inputs, ctx)
        moving = [x for x in plan if x[1]]
        by_folder = Counter(d for _, d, _ in moving)
        ctx.log(f"{len(plan)} arquivo(s) analisados; {len(moving)} seriam movidos.")
        for fname, count in by_folder.most_common():
            ctx.log(f"  {fname}: {count}")
        result = build_result(
            f"Pré-visualização: {len(moving)} de {len(plan)} arquivo(s) seriam movidos para "
            f"{len(by_folder)} pasta(s); {len(plan) - len(moving)} permaneceriam.",
            processed=len(plan), details=self._rows(plan),
        )
        return result

    def execute(self, inputs: dict, ctx) -> Result:
        plan = self._plan(inputs, ctx)
        base = Path(inputs["folder"])
        moving = [x for x in plan if x[1]]
        details, moved, errors, cancelled = [], 0, 0, False
        for i, (path, dest, why) in enumerate(moving, start=1):
            try:
                ctx.check_cancel()
                ctx.progress(i, len(moving), "Movendo arquivos")
                new_path = move_safe(path, base / dest)
                moved += 1
                details.append({"Arquivo": path.name, "Destino": dest, "Motivo": why,
                                "Resultado": "Movido", "Novo caminho": str(new_path)})
            except CancelledError:
                cancelled = True
                break
            except OSError as exc:
                errors += 1
                ctx.log(f"Erro ao mover '{path.name}': {exc}", "error")
                details.append({"Arquivo": path.name, "Destino": dest, "Motivo": why,
                                "Resultado": f"Erro: {exc}", "Novo caminho": ""})
        ctx.log(f"{moved} arquivo(s) movido(s), {errors} erro(s).")
        result = build_result(
            f"{moved} arquivo(s) movido(s) em {base}; {errors} erro(s)."
            + (" Execução cancelada antes de terminar." if cancelled else ""),
            processed=moved, errors=errors, details=details,
        )
        if cancelled:
            result.status = "cancelled"
        return result
