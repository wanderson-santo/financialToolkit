"""Histórico de execuções, configurações por módulo e favoritos (SQLite local).

Guarda metadados e parâmetros — nunca cópias de planilhas ou documentos.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime

SCHEMA = """
CREATE TABLE IF NOT EXISTS executions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT, module_id TEXT NOT NULL, module_name TEXT, module_version TEXT,
    mode TEXT NOT NULL, started_at TEXT NOT NULL, finished_at TEXT,
    status TEXT, summary TEXT,
    processed INTEGER DEFAULT 0, warnings INTEGER DEFAULT 0, errors INTEGER DEFAULT 0,
    params_json TEXT, output_files_json TEXT
);
CREATE TABLE IF NOT EXISTS execution_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    execution_id INTEGER NOT NULL, ts TEXT, level TEXT, message TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_exec ON execution_events(execution_id);
CREATE TABLE IF NOT EXISTS module_settings (
    module_id TEXT PRIMARY KEY, settings_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS favorites (module_id TEXT PRIMARY KEY);
"""


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class HistoryService:
    def __init__(self, db_file):
        self.db_file = str(db_file)
        with self._conn() as c:
            c.executescript(SCHEMA)
            # execuções que ficaram "em andamento" por fechamento abrupto do app
            c.execute("UPDATE executions SET status='interrupted' WHERE status='running'")

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
                (run_id, module.module_id, module.name, module.version, mode, _now(), "running",
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
                " SUM(CASE WHEN status='success' AND warnings=0 THEN 1 ELSE 0 END) AS ok,"
                " SUM(CASE WHEN status='partial_success' OR (status='success' AND warnings>0)"
                "     THEN 1 ELSE 0 END) AS alerts,"
                " SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) AS failed,"
                " SUM(CASE WHEN status='cancelled' THEN 1 ELSE 0 END) AS cancelled"
                " FROM executions WHERE mode='execute'"
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
