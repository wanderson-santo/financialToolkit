"""Detector de arquivos duplicados (mesmo conteúdo, nomes diferentes).

Baseado no script de duplicatas por tamanho + hash. Em vez de excluir, a ação
opcional MOVE as cópias para uma quarentena. O manifesto (grupo, origem,
destino e status) é gravado antes do primeiro movimento e atualizado de forma
atômica; se algo falhar, o estado parcial fica explícito.
"""
from __future__ import annotations

import csv
import os
from datetime import datetime
from pathlib import Path

from core.base_module import (
    CANCELLED, BaseModule, ParamSpec, Result, build_result,
)
from core.categories import CATEGORY_FILES
from core.exceptions import CancelledError, ToolkitError
from core.file_service import hash_file, iter_files, move_to, unique_path

ACTION_REPORT = "Apenas relatar"
ACTION_MOVE = "Mover duplicatas para a quarentena"
KEEP_OLDEST = "Mais antigo (data de modificação)"
KEEP_NEWEST = "Mais recente"
KEEP_SHORT = "Nome mais curto"

MANIFEST_HEADER = ["grupo", "origem", "destino", "status"]
STATUS_PENDING = "pendente"
STATUS_MOVED = "movida"
STATUS_ERROR = "erro"
STATUS_CANCELLED = "cancelado"


def _plan_destinations(dups, quarantine: Path) -> list[tuple[int, Path, Path]]:
    """Destino único para cada duplicata, antes de qualquer movimentação."""
    reserved: set[str] = set()
    plan = []
    for group_no, src in dups:
        candidate = quarantine / src.name
        suffix = 1
        while candidate.exists() or os.path.normcase(str(candidate)) in reserved:
            candidate = quarantine / f"{src.stem}_{suffix}{src.suffix}"
            suffix += 1
        reserved.add(os.path.normcase(str(candidate)))
        plan.append((group_no, src, candidate))
    return plan


def _write_manifest(path: Path, rows: list[list]) -> None:
    """Grava o manifesto de forma atômica (temporário + replace)."""
    tmp = path.with_name(f".{path.name}.tmp")
    try:
        with open(tmp, "w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.writer(fh, delimiter=";")
            writer.writerow(MANIFEST_HEADER)
            writer.writerows(rows)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def _pick_keeper(paths: list[Path], stats: dict, mode: str) -> tuple[Path, list[Path]]:
    if mode == KEEP_NEWEST:
        key = lambda p: (-stats[p][1], str(p))
    elif mode == KEEP_SHORT:
        key = lambda p: (len(p.name), stats[p][1], str(p))
    else:
        key = lambda p: (stats[p][1], str(p))
    ordered = sorted(paths, key=key)
    return ordered[0], ordered[1:]


class DuplicateFinder(BaseModule):
    module_id = "duplicate_finder"
    name = "Detector de arquivos duplicados"
    category = CATEGORY_FILES
    description = (
        "Encontra arquivos com conteúdo idêntico (tamanho + hash SHA-256), mesmo com nomes diferentes. "
        "Por padrão só relata; opcionalmente move as cópias para uma quarentena, sem excluir nada."
    )
    modifies_files = True
    params = [
        ParamSpec("folder", "Pasta a analisar", "folder"),
        ParamSpec("recursive", "Incluir subpastas", "bool", default=True),
        ParamSpec("action", "Ação sobre as duplicatas", "choice", default=ACTION_REPORT,
                  choices=[ACTION_REPORT, ACTION_MOVE]),
        ParamSpec("keep", "Qual cópia manter", "choice", default=KEEP_OLDEST,
                  choices=[KEEP_OLDEST, KEEP_NEWEST, KEEP_SHORT]),
        ParamSpec("quarantine", "Pasta de quarentena", "text", default="_Duplicatas_quarentena", required=False,
                  help="Nome de subpasta (dentro da pasta analisada) ou caminho completo."),
    ]

    def requires_confirmation(self, inputs: dict) -> bool:
        return inputs.get("action") == ACTION_MOVE

    def _quarantine_dir(self, inputs: dict) -> Path:
        q = Path((inputs.get("quarantine") or "_Duplicatas_quarentena").strip())
        return q if q.is_absolute() else Path(inputs["folder"]) / q

    def _scan(self, inputs: dict, ctx):
        folder = Path(inputs["folder"])
        quarantine = self._quarantine_dir(inputs)
        by_size: dict[int, list[Path]] = {}
        stats: dict[Path, tuple[int, float]] = {}
        zero_byte = 0
        for path in iter_files(folder, bool(inputs.get("recursive", True)), exclude=[quarantine]):
            ctx.check_cancel()
            try:
                st = path.stat()
            except OSError:
                continue
            if st.st_size == 0:
                zero_byte += 1
                continue
            stats[path] = (st.st_size, st.st_mtime)
            by_size.setdefault(st.st_size, []).append(path)
        ctx.log(f"{len(stats)} arquivo(s) encontrados ({zero_byte} vazio(s) ignorado(s)).")

        candidates = [p for group in by_size.values() if len(group) > 1 for p in group]
        by_hash: dict[str, list[Path]] = {}
        unreadable = 0
        for i, path in enumerate(candidates, start=1):
            ctx.check_cancel()
            ctx.progress(i, len(candidates), "Calculando hashes")
            try:
                by_hash.setdefault(hash_file(path), []).append(path)
            except OSError as exc:
                unreadable += 1
                ctx.log(f"Não foi possível ler '{path.name}': {exc}", "warning")
        groups = [g for g in by_hash.values() if len(g) > 1]
        groups.sort(key=lambda g: -stats[g[0]][0])
        return groups, stats, unreadable

    @staticmethod
    def _fmt(ts: float) -> str:
        return datetime.fromtimestamp(ts).strftime("%d/%m/%Y %H:%M")

    def _rows_and_plan(self, groups, stats, keep_mode):
        rows, to_move, wasted = [], [], 0
        for number, group in enumerate(groups, start=1):
            keeper, dups = _pick_keeper(group, stats, keep_mode)
            rows.append({"Grupo": number, "Arquivo": str(keeper), "Tamanho (KB)": round(stats[keeper][0] / 1024, 1),
                         "Modificado": self._fmt(stats[keeper][1]), "Ação": "Manter"})
            for d in dups:
                wasted += stats[d][0]
                to_move.append((number, d))
                rows.append({"Grupo": number, "Arquivo": str(d), "Tamanho (KB)": round(stats[d][0] / 1024, 1),
                             "Modificado": self._fmt(stats[d][1]), "Ação": "Duplicata"})
        return rows, to_move, wasted

    def preview(self, inputs: dict, ctx) -> Result:
        groups, stats, unreadable = self._scan(inputs, ctx)
        rows, dups, wasted = self._rows_and_plan(groups, stats, inputs.get("keep", KEEP_OLDEST))
        mb = wasted / (1024 * 1024)
        return build_result(
            f"{len(groups)} grupo(s) de duplicatas; {len(dups)} cópia(s) redundante(s) ocupando {mb:.1f} MB.",
            processed=len(dups), warnings=unreadable, details=rows,
        )

    def execute(self, inputs: dict, ctx) -> Result:
        groups, stats, unreadable = self._scan(inputs, ctx)
        rows, dups, wasted = self._rows_and_plan(groups, stats, inputs.get("keep", KEEP_OLDEST))
        mb = wasted / (1024 * 1024)
        if inputs.get("action") != ACTION_MOVE or not dups:
            return build_result(
                f"{len(groups)} grupo(s); {len(dups)} cópia(s) redundante(s) ({mb:.1f} MB). Nenhum arquivo alterado.",
                processed=len(dups), warnings=unreadable, details=rows,
            )

        quarantine = self._quarantine_dir(inputs)
        try:
            quarantine.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ToolkitError(
                f"Não foi possível criar a pasta de quarentena {quarantine}: {exc}"
            ) from exc

        plan = _plan_destinations(dups, quarantine)
        manifest_path = unique_path(quarantine / f"manifesto_{datetime.now():%Y%m%d_%H%M%S}.csv")
        manifest = [
            [group_no, str(src), str(dest), STATUS_PENDING] for group_no, src, dest in plan
        ]
        row_of = {str(src): i for i, (_, src, _) in enumerate(plan)}
        try:
            _write_manifest(manifest_path, manifest)
        except OSError as exc:
            raise ToolkitError(
                f"Não foi possível gravar o manifesto em {manifest_path}: {exc}. "
                "Nenhum arquivo foi movido."
            ) from exc

        moved, errors, cancelled, manifest_failed = 0, 0, False, False
        outcome: dict[str, str] = {}
        for i, (_, path, dest) in enumerate(plan, start=1):
            try:
                ctx.check_cancel()
                ctx.progress(i, len(plan), "Movendo duplicatas")
                move_to(path, dest)
            except CancelledError:
                cancelled = True
                break
            except OSError as exc:
                errors += 1
                outcome[str(path)] = f"Erro: {exc}"
                manifest[row_of[str(path)]][3] = f"{STATUS_ERROR}: {exc}"
                ctx.log(f"Erro ao mover '{path.name}': {exc}", "error")
                try:
                    _write_manifest(manifest_path, manifest)
                except OSError as write_exc:
                    manifest_failed = True
                    ctx.log(f"Falha ao atualizar o manifesto: {write_exc}", "error")
                    break
                continue

            moved += 1
            outcome[str(path)] = "Movida para a quarentena"
            manifest[row_of[str(path)]][3] = STATUS_MOVED
            try:
                _write_manifest(manifest_path, manifest)
            except OSError as exc:
                manifest_failed = True
                errors += 1
                outcome[str(path)] = "Movida; manifesto não atualizado"
                ctx.log(f"Arquivo movido, mas o manifesto não pôde ser atualizado: {exc}", "error")
                break

        if cancelled and not manifest_failed:
            for row in manifest:
                if row[3] == STATUS_PENDING:
                    row[3] = STATUS_CANCELLED
            try:
                _write_manifest(manifest_path, manifest)
            except OSError as exc:
                manifest_failed = True
                ctx.log(f"Falha ao finalizar o manifesto: {exc}", "error")

        for row in rows:
            if row["Ação"] == "Duplicata" and row["Arquivo"] in outcome:
                row["Ação"] = outcome[row["Arquivo"]]

        summary = f"{moved} duplicata(s) movida(s) para {quarantine} ({mb:.1f} MB); {errors} erro(s)."
        if cancelled:
            summary += " Execução cancelada antes de terminar."
        if manifest_failed:
            summary += " O manifesto pode estar desatualizado; confira os destinos na quarentena."
        result = build_result(
            summary, processed=moved, warnings=unreadable, errors=errors,
            output_files=[str(manifest_path)], details=rows,
            status=CANCELLED if cancelled else None,
        )
        return result
