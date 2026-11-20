import sqlite3
import unittest
from unittest import mock

from core import db_migrations
from core.db_migrations import SCHEMA_VERSION, apply_migrations, get_version
from core.exceptions import ToolkitError
from core.history_service import HistoryService
from tests.helpers import TempDirCase

LEGACY_SCHEMA = """
CREATE TABLE executions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT, module_id TEXT NOT NULL, module_name TEXT, module_version TEXT,
    mode TEXT NOT NULL, started_at TEXT NOT NULL, finished_at TEXT,
    status TEXT, summary TEXT,
    processed INTEGER DEFAULT 0, warnings INTEGER DEFAULT 0, errors INTEGER DEFAULT 0,
    params_json TEXT, output_files_json TEXT
);
CREATE TABLE execution_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    execution_id INTEGER NOT NULL, ts TEXT, level TEXT, message TEXT
);
CREATE INDEX idx_events_exec ON execution_events(execution_id);
CREATE TABLE module_settings (
    module_id TEXT PRIMARY KEY, settings_json TEXT NOT NULL
);
CREATE TABLE favorites (module_id TEXT PRIMARY KEY);
"""


class MigrationTests(TempDirCase):
    def open_history(self, path):
        # A retenção automática é desativada para os testes serem determinísticos.
        return HistoryService(path, retention_days=None, retention_keep=None)

    def _connect(self, path):
        conn = sqlite3.connect(path)
        self.addCleanup(conn.close)
        return conn

    def test_banco_novo_nasce_na_versao_atual(self):
        path = self.tmp / "novo.db"
        self.open_history(path)

        conn = self._connect(path)
        self.assertEqual(get_version(conn), SCHEMA_VERSION)
        names = {
            row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        self.assertTrue({"executions", "execution_events", "module_settings", "favorites"} <= names)
        self.assertIn("execution_details", names)
        indexes = {
            row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
        }
        self.assertIn("idx_events_exec", indexes)
        self.assertIn("idx_details_exec", indexes)
        self.assertTrue({"idx_exec_mode", "idx_exec_module", "idx_exec_started"} <= indexes)
        columns = {row[1] for row in conn.execute("PRAGMA table_info(executions)")}
        self.assertTrue({"details_file", "details_count"} <= columns)

    def test_banco_antigo_migra_sem_perder_dados(self):
        path = self.tmp / "antigo.db"
        conn = self._connect(path)
        conn.executescript(LEGACY_SCHEMA)
        cur = conn.execute(
            "INSERT INTO executions (module_id, module_name, module_version, mode, started_at,"
            " status, summary) VALUES ('m1', 'Módulo 1', '1.0', 'execute',"
            " '2026-01-01 10:00:00', 'success', 'execução antiga')"
        )
        exec_id = int(cur.lastrowid)
        conn.execute(
            "INSERT INTO execution_events (execution_id, ts, level, message)"
            " VALUES (?, '2026-01-01 10:00:01', 'info', 'evento antigo')",
            (exec_id,),
        )
        conn.execute(
            "INSERT INTO module_settings (module_id, settings_json) VALUES ('m1', '{\"x\": \"y\"}')"
        )
        conn.execute("INSERT INTO favorites (module_id) VALUES ('m1')")
        conn.commit()
        self.assertEqual(get_version(conn), 0)

        history = self.open_history(path)

        self.assertEqual(history.get(exec_id)["summary"], "execução antiga")
        self.assertEqual(history.events(exec_id)[0]["message"], "evento antigo")
        self.assertEqual(history.get_settings("m1"), {"x": "y"})
        self.assertEqual(history.favorites(), ["m1"])
        self.assertEqual(get_version(conn), SCHEMA_VERSION)

    def test_banco_v1_migra_para_v2(self):
        path = self.tmp / "v1.db"
        conn = self._connect(path)
        conn.executescript(LEGACY_SCHEMA)
        conn.execute("PRAGMA user_version = 1")
        cur = conn.execute(
            "INSERT INTO executions (module_id, module_name, module_version, mode, started_at,"
            " status, summary) VALUES ('m1', 'Módulo 1', '1.0', 'execute',"
            " '2026-01-01 10:00:00', 'success', 'execução v1')"
        )
        exec_id = int(cur.lastrowid)
        conn.commit()
        self.assertEqual(get_version(conn), 1)

        history = self.open_history(path)

        row = history.get(exec_id)
        self.assertEqual(row["summary"], "execução v1")
        self.assertIsNone(row["details_file"])
        self.assertEqual(row["details_count"], 0)
        self.assertEqual(history.details(exec_id), [])
        self.assertEqual(get_version(conn), SCHEMA_VERSION)

    def test_migracao_e_idempotente(self):
        path = self.tmp / "repetida.db"
        history = self.open_history(path)
        history.set_settings("m1", {"ok": True})

        self.open_history(path)
        conn = self._connect(path)
        for _ in range(2):
            self.assertEqual(apply_migrations(conn), SCHEMA_VERSION)
        self.assertEqual(get_version(conn), SCHEMA_VERSION)

        reopened = self.open_history(path)
        self.assertEqual(reopened.get_settings("m1"), {"ok": True})

    def test_versao_mais_nova_e_recusada(self):
        path = self.tmp / "futuro.db"
        conn = self._connect(path)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
        conn.commit()

        with self.assertRaises(ToolkitError) as ctx:
            self.open_history(path)

        self.assertIn(str(SCHEMA_VERSION + 1), str(ctx.exception))
        self.assertIn("Atualize", str(ctx.exception))
        self.assertEqual(get_version(conn), SCHEMA_VERSION + 1)

    def test_falha_nao_deixa_esquema_parcial(self):
        path = self.tmp / "falha.db"
        conn = self._connect(path)
        migrations = {
            1: (
                "CREATE TABLE primeira (x INTEGER)",
                "CREATE TABLE invalida (",
            )
        }
        with mock.patch.object(db_migrations, "SCHEMA_VERSION", 1), \
                mock.patch.object(db_migrations, "MIGRATIONS", migrations):
            with self.assertRaises(sqlite3.DatabaseError):
                apply_migrations(conn)

        self.assertEqual(get_version(conn), 0)
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='primeira'"
        ).fetchone()
        self.assertIsNone(row)
