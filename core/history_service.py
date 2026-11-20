"""Histórico de execuções, configurações por módulo e favoritos (SQLite local).

Guarda metadados e parâmetros. Os detalhes persistidos podem conter dados das
planilhas processadas, mas o aplicativo nunca guarda cópias dos arquivos.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import tempfile
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

from .base_module import (
    CANCELLED, FAILED, INTERRUPTED, PARTIAL, RUNNING, SUCCESS,
)
from .db_migrations import SCHEMA_VERSION, apply_migrations, get_version
from .exceptions import ToolkitError
from .logging_service import get_logger
from .paths import backups_dir, details_dir

_CORRUPTION_MARKERS = (
    "file is not a database",
    "database disk image is malformed",
    "malformed database schema",
    "file is encrypted or is not a database",
    "database corruption",
)

# Até este limite os detalhes ficam na tabela; acima disso vão para um JSONL.
DETAILS_INLINE_LIMIT = 1000
# Teto por execução: evita crescimento sem limite e mantém a exportação ágil.
DETAILS_MAX_ROWS = 50_000
# Política padrão de retenção do histórico.
DEFAULT_RETENTION_DAYS = 365
DEFAULT_RETENTION_KEEP = 5000


def _chunks(values: list[int], size: int = 900):
    for start in range(0, len(values), size):
        yield values[start:start + size]


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
    def __init__(
        self,
        db_file,
        details_root=None,
        backups_root=None,
        retention_days=DEFAULT_RETENTION_DAYS,
        retention_keep=DEFAULT_RETENTION_KEEP,
    ):
        self.db_file = str(db_file)
        self._details_root = Path(details_root) if details_root is not None else None
        self._backups_root = Path(backups_root) if backups_root is not None else None
        self._prepare_database()
        with self._conn() as c:
            # execuções que ficaram "em andamento" por fechamento abrupto do app
            c.execute(
                "UPDATE executions SET status=? WHERE status=?",
                (INTERRUPTED, RUNNING),
            )
        if retention_days is not None or retention_keep is not None:
            try:
                self.prune(days=retention_days, keep_last=retention_keep)
            except Exception:  # noqa: BLE001 - retenção não deve impedir o app de abrir
                get_logger().exception("Falha ao aplicar a retenção do histórico")

    def _prepare_database(self) -> None:
        """Ativa WAL, faz backup de banco antigo e aplica as migrações."""
        path = Path(self.db_file)
        existed = path.exists() and path.stat().st_size > 0
        with self._conn() as c:
            c.execute("PRAGMA journal_mode=WAL")
            version = get_version(c)

        if existed and version < SCHEMA_VERSION:
            try:
                backup = self.backup(reason="pre-migration")
            except (OSError, sqlite3.Error, ToolkitError) as exc:
                raise ToolkitError(
                    "Não foi possível criar o backup antes de migrar o banco do histórico. "
                    "A migração não foi aplicada; verifique o espaço e as permissões da pasta."
                ) from exc
            get_logger().info("Backup criado antes da migração em %s", backup)

        with self._conn() as c:
            apply_migrations(c)

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

    # ---- manutenção do banco ---------------------------------------------

    def _backups_dir(self) -> Path:
        if self._backups_root is not None:
            self._backups_root.mkdir(parents=True, exist_ok=True)
            return self._backups_root
        return backups_dir()

    def backup(self, reason: str = "manual", directory=None) -> Path:
        """Cria uma cópia consistente do banco e valida a integridade.

        Usa a API de backup do SQLite, que também copia transações ainda no WAL.
        """
        target_dir = Path(directory) if directory is not None else self._backups_dir()
        target_dir.mkdir(parents=True, exist_ok=True)
        slug = re.sub(r"[^a-z0-9]+", "-", str(reason).casefold()).strip("-") or "manual"
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        candidate = target_dir / f"finance_toolkit-{stamp}-{slug}.db"
        counter = 1
        while candidate.exists():
            candidate = target_dir / f"finance_toolkit-{stamp}-{slug}-{counter}.db"
            counter += 1

        source = sqlite3.connect(self.db_file, timeout=10)
        dest = sqlite3.connect(candidate)
        try:
            source.backup(dest)
            dest.commit()
            check = dest.execute("PRAGMA integrity_check").fetchone()
            if not check or check[0] != "ok":
                raise ToolkitError(
                    "O backup criado não passou na verificação de integridade"
                    f": {check[0] if check else 'sem resposta'}"
                )
        except BaseException:
            dest.close()
            source.close()
            for suffix in ("", "-wal", "-shm", "-journal"):
                Path(f"{candidate}{suffix}").unlink(missing_ok=True)
            raise
        dest.close()
        source.close()
        return candidate

    @staticmethod
    def _validate_backup(path: Path) -> None:
        try:
            conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
        except sqlite3.Error as exc:
            raise ToolkitError(f"Não foi possível abrir o backup {path}: {exc}") from exc
        try:
            try:
                check = conn.execute("PRAGMA integrity_check").fetchone()
                names = {
                    row[0]
                    for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
                }
                version = get_version(conn)
            except sqlite3.DatabaseError as exc:
                raise ToolkitError(
                    f"O arquivo {path} não é um backup válido do histórico."
                ) from exc
            if not check or check[0] != "ok":
                raise ToolkitError(
                    f"O backup {path} está corrompido: {check[0] if check else 'sem resposta'}"
                )
            if "executions" not in names:
                raise ToolkitError(f"O arquivo {path} não contém um histórico do Finance Toolkit.")
            if version > SCHEMA_VERSION:
                raise ToolkitError(
                    f"O backup está na versão {version}, mas este aplicativo suporta até "
                    f"{SCHEMA_VERSION}. Atualize o Finance Toolkit antes de restaurar."
                )
        finally:
            conn.close()

    def restore(self, backup_path) -> Path | None:
        """Restaura um backup validado e devolve o backup de segurança do estado atual.

        O banco atual é copiado antes da troca. Backups de versões anteriores são
        migrados em seguida; arquivos ``-wal``/``-shm`` antigos são removidos.
        """
        source = Path(backup_path)
        current = Path(self.db_file)
        if not source.exists():
            raise ToolkitError(f"Backup não encontrado: {source}")
        if current.exists() and source.resolve() == current.resolve():
            raise ToolkitError("Escolha um backup diferente do banco em uso.")
        self._validate_backup(source)

        safety = None
        if current.exists():
            try:
                safety = self.backup(reason="pre-restore")
            except (OSError, sqlite3.Error, ToolkitError):
                # Um banco atual corrompido não deve impedir a restauração.
                get_logger().warning(
                    "Não foi possível criar o backup de segurança antes de restaurar", exc_info=True
                )

        fd, temp_name = tempfile.mkstemp(
            prefix=f".{current.name}.", suffix=".restore", dir=current.parent
        )
        os.close(fd)
        temp = Path(temp_name)
        try:
            shutil.copyfile(source, temp)
            for suffix in ("-wal", "-shm"):
                Path(f"{current}{suffix}").unlink(missing_ok=True)
            os.replace(temp, current)
        except BaseException:
            temp.unlink(missing_ok=True)
            raise

        with self._conn() as c:
            c.execute("PRAGMA journal_mode=WAL")
            apply_migrations(c)
            c.execute(
                "UPDATE executions SET status=? WHERE status=?",
                (INTERRUPTED, RUNNING),
            )
        get_logger().info("Histórico restaurado de %s", source)
        return safety

    def prune(
        self,
        days: int | None = None,
        keep_last: int | None = None,
    ) -> dict:
        """Remove execuções antigas e além do limite de retenção.

        Uma execução só é removida se satisfizer **todos** os critérios
        informados: estar mais velha que ``days`` e ficar fora das ``keep_last``
        mais recentes. Execuções em andamento nunca são removidas. Ao remover a
        execução, eventos, detalhes e o JSONL externo também são apagados.
        """
        if days is None and keep_last is None:
            return {"executions": 0, "events": 0, "details": 0, "files": 0}
        if days is not None and days < 0:
            raise ValueError("days não pode ser negativo")
        if keep_last is not None and keep_last < 0:
            raise ValueError("keep_last não pode ser negativo")

        clauses = ["status != ?"]
        args: list = [RUNNING]
        if days is not None:
            cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
            clauses.append("started_at < ?")
            args.append(cutoff)
        if keep_last is not None:
            clauses.append("id NOT IN (SELECT id FROM executions ORDER BY id DESC LIMIT ?)")
            args.append(int(keep_last))

        result = {"executions": 0, "events": 0, "details": 0, "files": 0}
        with self._conn() as c:
            rows = c.execute(
                f"SELECT id, details_file FROM executions WHERE {' AND '.join(clauses)}",
                args,
            ).fetchall()
            ids = [int(row["id"]) for row in rows]
            for chunk in _chunks(ids):
                placeholders = ",".join("?" * len(chunk))
                result["events"] += c.execute(
                    f"DELETE FROM execution_events WHERE execution_id IN ({placeholders})", chunk
                ).rowcount
                result["details"] += c.execute(
                    f"DELETE FROM execution_details WHERE execution_id IN ({placeholders})", chunk
                ).rowcount
                result["executions"] += c.execute(
                    f"DELETE FROM executions WHERE id IN ({placeholders})", chunk
                ).rowcount

        for row in rows:
            try:
                path = self._details_path(row["details_file"])
            except OSError:
                get_logger().warning("Não foi possível acessar a pasta de detalhes", exc_info=True)
                continue
            if path is None or not path.exists():
                continue
            try:
                path.unlink()
                result["files"] += 1
            except OSError:
                get_logger().warning("Não foi possível apagar o arquivo de detalhes %s", path,
                                     exc_info=True)

        if result["executions"]:
            get_logger().info(
                "Retenção removeu %s execução(ões), %s evento(s), %s detalhe(s) e %s arquivo(s).",
                result["executions"], result["events"], result["details"], result["files"],
            )
        return result

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
        events = list(events)
        details = list(result.details or [])
        stored = details[:DETAILS_MAX_ROWS]
        if len(details) > DETAILS_MAX_ROWS:
            message = (
                f"Detalhes truncados: {len(stored)} de {len(details)} linhas persistidas."
            )
            get_logger().warning("Execução %s: %s", exec_id, message)
            events.append((_now(), "warning", message))

        details_file: str | None = None
        inline_rows = stored
        if len(stored) > DETAILS_INLINE_LIMIT:
            try:
                details_file = self._write_details_file(exec_id, stored)
                inline_rows = []
            except OSError:
                # Sem acesso à pasta de detalhes, preserva a evidência no banco.
                get_logger().exception(
                    "Falha ao gravar detalhes externos da execução %s; usando o banco.", exec_id
                )

        with self._conn() as c:
            c.execute("DELETE FROM execution_details WHERE execution_id=?", (exec_id,))
            c.executemany(
                "INSERT INTO execution_details (execution_id, seq, data_json) VALUES (?,?,?)",
                [
                    (exec_id, seq, json.dumps(item, ensure_ascii=False, default=str))
                    for seq, item in enumerate(inline_rows)
                ],
            )
            c.execute(
                "UPDATE executions SET finished_at=?, status=?, summary=?, processed=?, warnings=?,"
                " errors=?, output_files_json=?, details_file=?, details_count=? WHERE id=?",
                (_now(), result.status, result.summary, result.processed, result.warnings,
                 result.errors, json.dumps(result.output_files, ensure_ascii=False), details_file,
                 len(stored), exec_id),
            )
            c.executemany(
                "INSERT INTO execution_events (execution_id, ts, level, message) VALUES (?,?,?,?)",
                [(exec_id, ts, level, msg) for ts, level, msg in events],
            )

    # ---- detalhes das execuções -----------------------------------------

    def _details_dir(self) -> Path:
        if self._details_root is not None:
            self._details_root.mkdir(parents=True, exist_ok=True)
            return self._details_root
        return details_dir()

    def _details_path(self, value: str | None) -> Path | None:
        if not value:
            return None
        path = Path(value)
        return path if path.is_absolute() else self._details_dir() / path

    def _write_details_file(self, exec_id: int, rows: list[dict]) -> str:
        """Grava um JSONL compacto de forma atômica e devolve o nome do arquivo."""
        directory = self._details_dir()
        name = f"details-{int(exec_id)}.jsonl"
        fd, temp_name = tempfile.mkstemp(prefix=f".{name}.", suffix=".tmp", dir=directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
                for item in rows:
                    line = json.dumps(
                        item, ensure_ascii=False, default=str, separators=(",", ":")
                    )
                    fh.write(line)
                    fh.write("\n")
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(temp_name, directory / name)
        except BaseException:
            try:
                os.unlink(temp_name)
            except OSError:
                pass
            raise
        return name

    @staticmethod
    def _read_details_file(path: Path, limit: int | None, offset: int) -> list[dict]:
        rows: list[dict] = []
        with path.open(encoding="utf-8") as fh:
            for seq, line in enumerate(fh):
                if not line.strip():
                    continue
                if seq < offset:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    get_logger().warning("Linha inválida nos detalhes da execução em %s", path)
                    continue
                if limit is not None and len(rows) >= limit:
                    break
        return rows

    def details(self, exec_id: int, limit: int | None = None, offset: int = 0) -> list[dict]:
        """Devolve os detalhes salvos, com paginação opcional.

        Arquivos externos são lidos sob demanda; se estiverem indisponíveis, a
        consulta recorre às linhas mantidas no banco.
        """
        row = self.get(exec_id)
        if not row:
            return []
        try:
            external = self._details_path(row.get("details_file"))
            if external is not None:
                return self._read_details_file(external, limit, offset)
        except (OSError, UnicodeDecodeError):
            get_logger().exception("Falha ao ler detalhes externos da execução %s", exec_id)

        sql = "SELECT data_json FROM execution_details WHERE execution_id=? ORDER BY seq"
        args: list = [exec_id]
        if limit is not None:
            sql += " LIMIT ? OFFSET ?"
            args.extend([int(limit), int(offset)])
        elif offset:
            sql += " LIMIT -1 OFFSET ?"
            args.append(int(offset))
        with self._conn() as c:
            rows = c.execute(sql, args).fetchall()
        out: list[dict] = []
        for item in rows:
            try:
                out.append(json.loads(item["data_json"]))
            except json.JSONDecodeError:
                get_logger().warning("Detalhe inválido na execução %s", exec_id)
        return out

    def all_details(self, exec_id: int) -> list[dict]:
        """Todos os detalhes salvos, para exportação."""
        return self.details(exec_id)

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
