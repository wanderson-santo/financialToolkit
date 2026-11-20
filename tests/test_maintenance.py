import sqlite3
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from core.base_module import Result, RUNNING, SUCCESS
from core.db_migrations import SCHEMA_VERSION
from core.exceptions import ToolkitError
from core.history_service import DETAILS_INLINE_LIMIT, HistoryService
from tests.helpers import TempDirCase
from tests.test_migrations import LEGACY_SCHEMA


class Module:
    module_id, name, version = "m1", "Módulo 1", "1.0"


class MaintenanceTests(TempDirCase):
    def setUp(self):
        super().setUp()
        self.db = self.tmp / "historico.db"
        self.details_root = self.tmp / "details"
        self.backups_root = self.tmp / "backups"
        self.history = self.open_history()

    def open_history(self, **kwargs):
        options = dict(
            details_root=self.details_root,
            backups_root=self.backups_root,
            retention_days=None,
            retention_keep=None,
        )
        options.update(kwargs)
        return HistoryService(self.db, **options)

    def add(self, summary="ok", started_at=None, finished=True, details=None, events=None):
        exec_id = self.history.start(Module, "execute", {})
        if finished:
            self.history.finish(
                exec_id,
                Result(status=SUCCESS, summary=summary, details=details or []),
                events or [],
            )
        if started_at is not None:
            with self.history._conn() as c:
                c.execute("UPDATE executions SET started_at=? WHERE id=?", (started_at, exec_id))
        return exec_id

    @staticmethod
    def days_ago(days):
        return (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

    def test_wal_ativo(self):
        with self.history._conn() as c:
            self.assertEqual(c.execute("PRAGMA journal_mode").fetchone()[0].casefold(), "wal")

    def test_consultas_filtradas_usam_indice(self):
        queries = {
            "idx_exec_mode": ("SELECT * FROM executions WHERE mode=? ORDER BY id DESC", ("execute",)),
            "idx_events_exec": (
                "SELECT * FROM execution_events WHERE execution_id=? ORDER BY id", (1,)
            ),
            "idx_details_exec": (
                "SELECT * FROM execution_details WHERE execution_id=? ORDER BY seq", (1,)
            ),
        }
        with self.history._conn() as c:
            for expected, (sql, args) in queries.items():
                with self.subTest(indice=expected):
                    plan = " ".join(
                        row[3] for row in c.execute("EXPLAIN QUERY PLAN " + sql, args)
                    )
                    self.assertIn(expected, plan)

    def test_retencao_por_data(self):
        old = self.add(
            started_at=self.days_ago(40),
            details=[{"a": 1}, {"b": 2}],
            events=[("2026-01-01 10:00:00", "info", "evento antigo")],
        )
        recent = self.add(started_at=self.days_ago(20))
        current = self.add()

        result = self.history.prune(days=30, keep_last=None)

        self.assertEqual(result, {"executions": 1, "events": 1, "details": 2, "files": 0})
        self.assertIsNone(self.history.get(old))
        self.assertIsNotNone(self.history.get(recent))
        self.assertIsNotNone(self.history.get(current))

    def test_retencao_por_quantidade_preserva_os_mais_recentes(self):
        ids = [self.add(started_at=self.days_ago(60)) for _ in range(4)]

        result = self.history.prune(days=30, keep_last=2)

        self.assertEqual(result["executions"], 2)
        self.assertEqual(
            [row["id"] for row in self.history.recent(10)],
            list(reversed(ids[-2:])),
        )

    def test_retencao_nunca_remove_execucao_em_andamento(self):
        running = self.add(finished=False, started_at=self.days_ago(400))

        result = self.history.prune(days=1, keep_last=0)

        self.assertEqual(result["executions"], 0)
        self.assertEqual(self.history.get(running)["status"], RUNNING)

    def test_retencao_apaga_arquivo_externo_de_detalhes(self):
        old = self.add(
            started_at=self.days_ago(40),
            details=[{"n": n} for n in range(DETAILS_INLINE_LIMIT + 1)],
        )
        path = self.details_root / self.history.get(old)["details_file"]
        self.assertTrue(path.exists())

        result = self.history.prune(days=30, keep_last=0)

        self.assertEqual(result["executions"], 1)
        self.assertEqual(result["files"], 1)
        self.assertFalse(path.exists())
        self.assertIsNone(self.history.get(old))

    def test_retencao_automatica_ao_abrir(self):
        old = self.add(started_at=self.days_ago(10))

        reopened = self.open_history(retention_days=1, retention_keep=0)

        self.assertIsNone(reopened.get(old))

    def test_retencao_valida_argumentos(self):
        with self.assertRaises(ValueError):
            self.history.prune(days=-1)
        with self.assertRaises(ValueError):
            self.history.prune(keep_last=-1)
        self.assertEqual(
            self.history.prune(),
            {"executions": 0, "events": 0, "details": 0, "files": 0},
        )

    def test_backup_restauravel(self):
        first = self.add(summary="primeira")
        backup = self.history.backup(reason="teste", directory=self.backups_root)
        second = self.add(summary="segunda")

        safety = self.history.restore(backup)

        self.assertIsNotNone(safety)
        self.assertTrue(safety.exists())
        self.assertEqual(self.history.get(first)["summary"], "primeira")
        self.assertIsNone(self.history.get(second))
        with self.history._conn() as c:
            self.assertEqual(c.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(c.execute("PRAGMA journal_mode").fetchone()[0].casefold(), "wal")

    def test_restauracao_funciona_com_banco_atual_corrompido(self):
        first = self.add(summary="preservada no backup")
        backup = self.history.backup(reason="teste", directory=self.backups_root)
        for suffix in ("-wal", "-shm"):
            Path(f"{self.db}{suffix}").unlink(missing_ok=True)
        self.db.write_bytes(b"banco atual corrompido")

        with self.assertLogs("finance_toolkit", level="WARNING"):
            safety = self.history.restore(backup)

        self.assertIsNone(safety)
        self.assertEqual(self.history.get(first)["summary"], "preservada no backup")

    def test_backup_antes_da_migracao(self):
        path = self.tmp / "legado.db"
        conn = sqlite3.connect(path)
        self.addCleanup(conn.close)
        conn.executescript(LEGACY_SCHEMA)
        cur = conn.execute(
            "INSERT INTO executions (module_id, module_name, module_version, mode, started_at,"
            " status, summary) VALUES ('m1', 'Módulo 1', '1.0', 'execute',"
            " '2026-01-01 10:00:00', 'success', 'legado')"
        )
        exec_id = int(cur.lastrowid)
        conn.execute("PRAGMA user_version = 1")
        conn.commit()
        conn.close()

        history = HistoryService(
            path, backups_root=self.backups_root, retention_days=None, retention_keep=None
        )

        backups = list(self.backups_root.glob("finance_toolkit-*-pre-migration.db"))
        self.assertEqual(len(backups), 1)
        backup_conn = sqlite3.connect(backups[0])
        self.addCleanup(backup_conn.close)
        self.assertEqual(backup_conn.execute("PRAGMA user_version").fetchone()[0], 1)
        self.assertEqual(backup_conn.execute("SELECT summary FROM executions").fetchone()[0], "legado")
        self.assertIsNotNone(history.get(exec_id))

    def test_backup_invalido_e_recusado_sem_alterar_o_banco(self):
        current = self.add(summary="atual")
        bad = self.tmp / "invalido.db"
        bad.write_bytes(b"isto nao e um banco")

        with self.assertRaises(ToolkitError):
            self.history.restore(bad)

        self.assertEqual(self.history.get(current)["summary"], "atual")
        self.assertEqual(len(self.history.all_details(current)), 0)

    def test_backup_de_versao_futura_e_recusado(self):
        future = self.tmp / "futuro.db"
        conn = sqlite3.connect(future)
        self.addCleanup(conn.close)
        conn.execute("CREATE TABLE executions (id INTEGER PRIMARY KEY)")
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
        conn.commit()
        conn.close()

        with self.assertRaises(ToolkitError) as ctx:
            self.history.restore(future)

        self.assertIn(str(SCHEMA_VERSION + 1), str(ctx.exception))
