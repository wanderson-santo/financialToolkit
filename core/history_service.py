"""Histórico de execuções, configurações por módulo e favoritos (SQLite local).

Guarda metadados e parâmetros — nunca cópias de planilhas ou documentos.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from .base_module import (
    CANCELLED, FAILED, INTERRUPTED, PARTIAL, RUNNING, SUCCESS,
)
from .db_migrations import apply_migrations
from .exceptions import ToolkitError
from .logging_service import get_logger

_CORRUPTION_MARKERS = (
    "file is not a database",
    "database disk image is malformed",
    "malformed database schema",
    "file is encrypted or is not a database",
    "database corruption",
)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _is_corruption_error(exc: sqlite3.DatabaseError) -> bool:
    message = str(exc).casefold()
    return any(marker in message for marker in _CORRUPTION_MARKERS)


def _corrupt_backup_path(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    candidate = path.with_name(f"{path.name}.corrupt-{stamp}")
    counter = 1
    while candidate.exists():
        candidate = path.with_name(f"{path.name}.corrupt-{stamp}-{counter}")
        counter += 1
    return candidate


def _quarantine_database(path: Path) -> Path:
    """Renomeia o banco inválido (e sidecars) sem apagar o conteúdo."""
    backup = _corrupt_backup_path(path)
    try:
        path.rename(backup)
    except OSError as exc:
        raise ToolkitError(
            "O banco de dados do histórico parece corrompido, mas não foi possível "
            f"preservá-lo em {backup}. Verifique as permissões da pasta e tente novamente."
        ) from exc

    for suffix in ("-wal", "-shm"):
        sidecar = Path(f"{path}{suffix}")
        if sidecar.exists():
            try:
                sidecar.rename(Path(f"{backup}{suffix}"))
            except OSError as exc:
                get_logger().error("Não foi possível preservar o arquivo %s", sidecar, exc_info=True)
                raise ToolkitError(
                    f"O banco foi preservado em {backup}, mas não foi possível mover {sidecar}. "
                    "Feche o aplicativo, mova ou renomeie esse arquivo manualmente e tente novamente."
                ) from exc
    return backup


class HistoryService:
    def __init__(self, db_file):
        self.db_file = str(db_file)
        with self._conn() as c:
            apply_migrations(c)
            # execuções que ficaram "em andamento" por fechamento abrupto do app
            c.execute(
                "UPDATE executions SET status=? WHERE status=?",
                (INTERRUPTED, RUNNING),
            )

    @classmethod
    def open_with_recovery(cls, db_file, on_recover=None) -> "HistoryService":
        """Abre o histórico e recupera apenas corrupção confirmada do SQLite.

        O arquivo inválido é renomeado para ``<nome>.corrupt-<timestamp>``.
        Erros de permissão, pasta ou bloqueio não são tratados como corrupção
        e continuam sendo propagados para a inicialização exibir a mensagem
        adequada.
        """
        path = Path(db_file)
        try:
            return cls(path)
        except sqlite3.DatabaseError as exc:
            if not _is_corruption_error(exc):
                raise
            backup = _quarantine_database(path)
            logger = get_logger()
            logger.error("Banco de dados corrompido preservado em %s: %s", backup, exc)
            history = cls(path)
            logger.info("Novo banco de dados criado em %s", path)
            if on_recover is not None:
                try:
                    on_recover(backup, exc)
                except Exception:  # noqa: BLE001 - falha de aviso não deve impedir o app
                    logger.exception("Falha ao notificar a recuperação do banco")
            return history

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_file, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # ---- execuções -------------------------------------------------------

    def start(self, module, mode: str, params: dict, run_id: str = "") -> int:
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO executions (run_id, module_id, module_name, module_version, mode,"
                " started_at, status, params_json) VALUES (?,?,?,?,?,?,?,?)",
                (run_id, module.module_id, module.name, module.version, mode, _now(), RUNNING,
                 json.dumps(params, ensure_ascii=False, default=str)),
            )
            return int(cur.lastrowid)

    def finish(self, exec_id: int, result, events: list[tuple[str, str, str]]) -> None:
        with self._conn() as c:
            c.execute(
                "UPDATE executions SET finished_at=?, status=?, summary=?, processed=?, warnings=?,"
                " errors=?, output_files_json=? WHERE id=?",
                (_now(), result.status, result.summary, result.processed, result.warnings,
                 result.errors, json.dumps(result.output_files, ensure_ascii=False), exec_id),
            )
            c.executemany(
                "INSERT INTO execution_events (execution_id, ts, level, message) VALUES (?,?,?,?)",
                [(exec_id, ts, level, msg) for ts, level, msg in events],
            )

    def recent(self, limit: int = 200, mode: str | None = None) -> list[dict]:
        sql = "SELECT * FROM executions"
        args: list = []
        if mode:
            sql += " WHERE mode=?"
            args.append(mode)
        sql += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        with self._conn() as c:
            return [dict(r) for r in c.execute(sql, args).fetchall()]

    def get(self, exec_id: int) -> dict | None:
        with self._conn() as c:
            row = c.execute("SELECT * FROM executions WHERE id=?", (exec_id,)).fetchone()
            return dict(row) if row else None

    def events(self, exec_id: int) -> list[dict]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT ts, level, message FROM execution_events WHERE execution_id=? ORDER BY id",
                (exec_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def stats(self) -> dict:
        """Contadores das execuções reais (não conta pré-visualizações)."""
        with self._conn() as c:
            r = c.execute(
                "SELECT COUNT(*) AS total,"
                " SUM(CASE WHEN status=? AND warnings=0 THEN 1 ELSE 0 END) AS ok,"
                " SUM(CASE WHEN status=? OR (status=? AND warnings>0) THEN 1 ELSE 0 END) AS alerts,"
                " SUM(CASE WHEN status=? THEN 1 ELSE 0 END) AS failed,"
                " SUM(CASE WHEN status=? THEN 1 ELSE 0 END) AS cancelled"
                " FROM executions WHERE mode='execute'",
                (SUCCESS, PARTIAL, SUCCESS, FAILED, CANCELLED),
            ).fetchone()
            return {k: int(r[k] or 0) for k in ("total", "ok", "alerts", "failed", "cancelled")}

    def recent_modules(self, limit: int = 5) -> list[str]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT module_id, MAX(id) AS last FROM executions GROUP BY module_id"
                " ORDER BY last DESC LIMIT ?", (limit,)
            ).fetchall()
            return [r["module_id"] for r in rows]

    # ---- configurações por módulo ---------------------------------------

    def get_settings(self, module_id: str) -> dict:
        with self._conn() as c:
            row = c.execute(
                "SELECT settings_json FROM module_settings WHERE module_id=?", (module_id,)
            ).fetchone()
        if not row:
            return {}
        try:
            return json.loads(row["settings_json"])
        except json.JSONDecodeError:
            return {}

    def set_settings(self, module_id: str, settings: dict) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT INTO module_settings (module_id, settings_json) VALUES (?,?)"
                " ON CONFLICT(module_id) DO UPDATE SET settings_json=excluded.settings_json",
                (module_id, json.dumps(settings, ensure_ascii=False, default=str)),
            )

    # ---- favoritos --------------------------------------------------------

    def favorites(self) -> list[str]:
        with self._conn() as c:
            return [r["module_id"] for r in c.execute("SELECT module_id FROM favorites ORDER BY rowid")]

    def is_favorite(self, module_id: str) -> bool:
        return module_id in self.favorites()

    def toggle_favorite(self, module_id: str) -> bool:
        """Alterna o favorito e devolve o novo estado."""
        with self._conn() as c:
            exists = c.execute("SELECT 1 FROM favorites WHERE module_id=?", (module_id,)).fetchone()
            if exists:
                c.execute("DELETE FROM favorites WHERE module_id=?", (module_id,))
                return False
            c.execute("INSERT INTO favorites (module_id) VALUES (?)", (module_id,))
            return True
