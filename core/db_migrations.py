"""Migrações incrementais do banco SQLite do histórico.

Cada chave de ``MIGRATIONS`` é a versão de destino e contém instruções SQL
idempotentes. A versão atual fica em ``PRAGMA user_version``; a migração roda
dentro de um savepoint, então uma falha não deixa tabelas ou índices parciais.
"""
from __future__ import annotations

import sqlite3

from .exceptions import ToolkitError

MIGRATIONS: dict[int, tuple[str, ...]] = {
    1: (
        """
        CREATE TABLE IF NOT EXISTS executions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT, module_id TEXT NOT NULL, module_name TEXT, module_version TEXT,
            mode TEXT NOT NULL, started_at TEXT NOT NULL, finished_at TEXT,
            status TEXT, summary TEXT,
            processed INTEGER DEFAULT 0, warnings INTEGER DEFAULT 0, errors INTEGER DEFAULT 0,
            params_json TEXT, output_files_json TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS execution_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            execution_id INTEGER NOT NULL, ts TEXT, level TEXT, message TEXT
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_events_exec ON execution_events(execution_id)",
        """
        CREATE TABLE IF NOT EXISTS module_settings (
            module_id TEXT PRIMARY KEY, settings_json TEXT NOT NULL
        )
        """,
        "CREATE TABLE IF NOT EXISTS favorites (module_id TEXT PRIMARY KEY)",
    ),
    2: (
        "ALTER TABLE executions ADD COLUMN details_file TEXT",
        "ALTER TABLE executions ADD COLUMN details_count INTEGER DEFAULT 0",
        """
        CREATE TABLE IF NOT EXISTS execution_details (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            execution_id INTEGER NOT NULL,
            seq INTEGER NOT NULL,
            data_json TEXT NOT NULL
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_details_exec ON execution_details(execution_id, seq)",
    ),
    3: (
        "CREATE INDEX IF NOT EXISTS idx_exec_mode ON executions(mode, id DESC)",
        "CREATE INDEX IF NOT EXISTS idx_exec_module ON executions(module_id, id DESC)",
        "CREATE INDEX IF NOT EXISTS idx_exec_started ON executions(started_at)",
    ),
}

SCHEMA_VERSION = max(MIGRATIONS)


def get_version(conn: sqlite3.Connection) -> int:
    """Lê a versão do esquema gravada em ``PRAGMA user_version``."""
    return int(conn.execute("PRAGMA user_version").fetchone()[0])


def _rollback_migration(conn: sqlite3.Connection) -> None:
    try:
        conn.execute("ROLLBACK TO SAVEPOINT schema_migration")
        conn.execute("RELEASE SAVEPOINT schema_migration")
    except sqlite3.Error:
        pass


def apply_migrations(conn: sqlite3.Connection) -> int:
    """Aplica as migrações pendentes e devolve a versão final.

    Um banco novo (versão 0) nasce na versão atual. Bancos já atualizados são
    ignorados, tornando a operação idempotente. Um banco criado por uma versão
    mais nova do aplicativo é recusado para não ser lido com esquema errado.
    """
    version = get_version(conn)
    if version > SCHEMA_VERSION:
        raise ToolkitError(
            f"O banco de dados do histórico está na versão {version}, mas este aplicativo "
            f"suporta até a versão {SCHEMA_VERSION}. Atualize o Finance Toolkit antes de abrir."
        )
    if version == SCHEMA_VERSION:
        return version

    conn.execute("SAVEPOINT schema_migration")
    try:
        for target in range(version + 1, SCHEMA_VERSION + 1):
            for statement in MIGRATIONS[target]:
                conn.execute(statement)
            conn.execute(f"PRAGMA user_version = {int(target)}")
        conn.execute("RELEASE SAVEPOINT schema_migration")
    except sqlite3.DatabaseError:
        # Corrupção continua sendo reconhecida por HistoryService.open_with_recovery.
        _rollback_migration(conn)
        raise
    except Exception as exc:
        _rollback_migration(conn)
        raise ToolkitError(
            f"Não foi possível migrar o banco do histórico da versão {version} para "
            f"{SCHEMA_VERSION}. Nenhuma alteração parcial foi mantida."
        ) from exc
    return SCHEMA_VERSION
