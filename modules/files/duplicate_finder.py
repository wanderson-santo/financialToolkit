"""Detector de arquivos duplicados (mesmo conteúdo, nomes diferentes).

Baseado no script de duplicatas por tamanho + hash. Em vez de excluir, a ação
opcional MOVE as cópias para uma quarentena e grava um manifesto CSV com
origem e destino de cada arquivo (permite desfazer).
"""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from core.base_module import BaseModule, ParamSpec, Result, build_result
from core.categories import CATEGORY_FILES
from core.exceptions import CancelledError
from core.file_service import hash_file, iter_files, move_safe

ACTION_REPORT = "Apenas relatar"
ACTION_MOVE = "Mover duplicatas para a quarentena"
KEEP_OLDEST = "Mais antigo (data de modificação)"
KEEP_NEWEST = "Mais recente"
KEEP_SHORT = "Nome mais curto"


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
        manifest, moved, errors, cancelled = [], 0, 0, False
        outcome: dict[str, str] = {}
        for i, (group_no, path) in enumerate(dups, start=1):
            try:
                ctx.check_cancel()
                ctx.progress(i, len(dups), "Movendo duplicatas")
                new_path = move_safe(path, quarantine)
                moved += 1
                outcome[str(path)] = "Movida para a quarentena"
                manifest.append([group_no, str(path), str(new_path)])
            except CancelledError:
                cancelled = True
                break
            except OSError as exc:
                errors += 1
                outcome[str(path)] = f"Erro: {exc}"
                ctx.log(f"Erro ao mover '{path.name}': {exc}", "error")
        for row in rows:
            if row["Ação"] == "Duplicata" and row["Arquivo"] in outcome:
                row["Ação"] = outcome[row["Arquivo"]]

        output_files: list[str] = []
        if manifest:
            manifest_path = quarantine / f"manifesto_{datetime.now():%Y%m%d_%H%M%S}.csv"
            with open(manifest_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f, delimiter=";")
                writer.writerow(["grupo", "origem", "destino"])
                writer.writerows(manifest)
            output_files.append(str(manifest_path))
        result = build_result(
            f"{moved} duplicata(s) movida(s) para {quarantine} ({mb:.1f} MB); {errors} erro(s)."
            + (" Execução cancelada antes de terminar." if cancelled else ""),
            processed=moved, warnings=unreadable, errors=errors, output_files=output_files, details=rows,
        )
        if cancelled:
            result.status = "cancelled"
        return result
