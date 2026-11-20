"""Páginas do aplicativo: início, módulo (genérica), histórico e utilitário planejado."""
from __future__ import annotations

import json
import queue
import threading
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, scrolledtext, ttk

from app import theme
from app.services import Services
from app.utils import open_path
from app.widgets import ParamForm, ResultTable, ScrollFrame
from core.base_module import (
    CANCELLED, FAILED, INTERRUPTED, PARTIAL, STATUS_LABELS, SUCCESS, BaseModule, Result,
)
from core.exceptions import CancelledError, ToolkitError
from core.execution_context import ExecutionContext
from core.export_service import export_rows
from core.logging_service import get_logger
from core.operation_coordinator import OperationBusyError

STATUS_COLORS = {
    SUCCESS: theme.ACCENT, PARTIAL: theme.WARN, FAILED: theme.ERR,
    CANCELLED: theme.WARN, INTERRUPTED: theme.WARN,
}
STATUS_ICONS = {SUCCESS: "✔", PARTIAL: "⚠", FAILED: "✘", CANCELLED: "⏹", INTERRUPTED: "⏸"}
MODE_LABELS = {"execute": "Execução", "preview": "Pré-visualização"}
DETAILS_PREVIEW = 200


def _short_date(ts: str | None) -> str:
    try:
        return datetime.strptime(ts or "", "%Y-%m-%d %H:%M:%S").strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return ts or ""


# ---------------------------------------------------------------------------
# Página de módulo (genérica: formulário + pré-visualização + execução)
# ---------------------------------------------------------------------------

class ModulePage(ttk.Frame):
    def __init__(self, parent, module: BaseModule, services: Services):
        super().__init__(parent)
        self.module = module
        self.history = services.history
        self.config = services.config
        self.coordinator = services.coordinator
        self._holds_operation = False
        self._queue: queue.Queue = queue.Queue()
        self._cancel = threading.Event()
        self._events: list[tuple[str, str, str]] = []
        self._exec_id: int | None = None
        self._run_id = ""
        self._last_result: Result | None = None
        self._mode = ""
        self._running = False
        self._finished = True
        self._build()
        self.form.load(self.config.module_inputs(module.module_id))

    # ---- interface ------------------------------------------------------------

    def _build(self) -> None:
        m = self.module
        header = ttk.Frame(self)
        header.pack(fill="x", padx=24, pady=(18, 0))
        ttk.Label(header, text=m.name, style="Title.TLabel").pack(side="left")
        self.btn_fav = ttk.Button(header, text="", style="Ghost.TButton", command=self._toggle_favorite)
        self.btn_fav.pack(side="right")
        self._refresh_fav()
        ttk.Label(self, text=f"{m.category}  ·  v{m.version}", style="Muted.TLabel").pack(anchor="w", padx=24)
        ttk.Label(self, text=m.description, wraplength=820, justify="left").pack(anchor="w", padx=24, pady=(6, 10))

        paned = ttk.PanedWindow(self, orient="vertical")
        paned.pack(fill="both", expand=True, padx=24, pady=(0, 12))
        top, bottom = ttk.Frame(paned), ttk.Frame(paned)
        paned.add(top, weight=1)
        paned.add(bottom, weight=1)

        scroll = ScrollFrame(top)
        scroll.pack(fill="both", expand=True)
        self.form = ParamForm(scroll.inner, m.params)
        self.form.pack(fill="x", expand=True)

        actions = ttk.Frame(top)
        actions.pack(fill="x", pady=(8, 0))
        self.btn_preview = ttk.Button(actions, text="👁  Pré-visualizar", command=lambda: self._start("preview"))
        self.btn_run = ttk.Button(actions, text="▶  Executar", style="Accent.TButton",
                                  command=lambda: self._start("execute"))
        self.btn_cancel = ttk.Button(actions, text="⏹  Cancelar", style="Danger.TButton",
                                     command=self._cancel_run, state="disabled")
        self.btn_export = ttk.Button(actions, text="💾  Exportar resultado", command=self._export, state="disabled")
        self.btn_open = ttk.Button(actions, text="📂  Abrir pasta de saída", command=self._open_output,
                                   state="disabled")
        for b in (self.btn_preview, self.btn_run, self.btn_cancel, self.btn_export, self.btn_open):
            b.pack(side="left", padx=(0, 8))

        prog = ttk.Frame(bottom)
        prog.pack(fill="x", pady=(8, 2))
        self.status_var = tk.StringVar(value="Pronto.")
        ttk.Label(prog, textvariable=self.status_var, style="Muted.TLabel").pack(anchor="w")
        self.bar = ttk.Progressbar(prog, mode="determinate", maximum=100)
        self.bar.pack(fill="x", pady=4)

        notebook = ttk.Notebook(bottom)
        notebook.pack(fill="both", expand=True)
        tab_result, tab_log = ttk.Frame(notebook), ttk.Frame(notebook)
        notebook.add(tab_result, text="Resultado")
        notebook.add(tab_log, text="Log")
        self.summary_var = tk.StringVar(value="")
        self.summary_label = ttk.Label(tab_result, textvariable=self.summary_var, wraplength=800, justify="left")
        self.summary_label.pack(anchor="w", padx=8, pady=6)
        self.table = ResultTable(tab_result)
        self.table.pack(fill="both", expand=True)
        self.log_text = scrolledtext.ScrolledText(
            tab_log, height=8, font=theme.MONO, bg=theme.FIELD, fg=theme.TEXT, relief="flat",
            padx=8, pady=6, state="disabled", insertbackground=theme.ACCENT)
        self.log_text.pack(fill="both", expand=True)
        self.log_text.tag_config("info", foreground=theme.TEXT)
        self.log_text.tag_config("warning", foreground=theme.WARN)
        self.log_text.tag_config("error", foreground=theme.ERR)

    # ---- favoritos --------------------------------------------------------------

    def _refresh_fav(self) -> None:
        fav = self.history.is_favorite(self.module.module_id)
        self.btn_fav.configure(text="★ Favorito" if fav else "☆ Favoritar")

    def _toggle_favorite(self) -> None:
        self.history.toggle_favorite(self.module.module_id)
        self._refresh_fav()

    # ---- execução ---------------------------------------------------------------

    def _set_running(self, running: bool) -> None:
        self._running = running
        idle = "disabled" if running else "normal"
        self.btn_preview.configure(state=idle)
        self.btn_run.configure(state=idle)
        self.btn_cancel.configure(state="normal" if running else "disabled")

    @property
    def is_running(self) -> bool:
        return self._running

    def _release_operation(self) -> None:
        if self._holds_operation:
            self._holds_operation = False
            self.coordinator.release(self.module.module_id)

    def request_cancel(self) -> None:
        if self._running:
            self._cancel_run()

    def interrupt(self, reason: str) -> None:
        """Finaliza o histórico quando o encerramento não pode esperar mais."""
        if not self._running:
            return
        self._finish(Result(status=INTERRUPTED, summary=reason, is_preview=self._mode == "preview"))

    def _start(self, mode: str) -> None:
        if self._running:
            return
        values = self.form.get_values()
        issues = self.module.validate(values)
        errors = [i.message for i in issues if i.level == "error"]
        if errors:
            messagebox.showwarning("Corrija antes de continuar", "\n".join("• " + e for e in errors))
            return
        warnings = [i.message for i in issues if i.level == "warning"]
        if warnings and not messagebox.askyesno(
                "Avisos", "\n".join("• " + w for w in warnings) + "\n\nDeseja continuar mesmo assim?"):
            return
        if mode == "execute" and self.module.requires_confirmation(values):
            if not messagebox.askyesno(
                    "Confirmar execução",
                    "Esta execução vai alterar arquivos no seu computador.\n\n"
                    "Você já conferiu a pré-visualização?\n\nDeseja continuar?"):
                return

        if mode == "execute":
            try:
                self.coordinator.acquire(self.module.module_id, self.module.name)
            except OperationBusyError as exc:
                messagebox.showwarning("Operação em andamento", str(exc))
                return
            self._holds_operation = True

        try:
            self.config.save_module_inputs(self.module.module_id, values)
            self._cancel.clear()
            self._mode = mode
            self._finished = False
            self._events = []
            self._last_result = None
            run_id = ExecutionContext.new_run_id()
            self._run_id = run_id
            self._exec_id = self.history.start(self.module, mode, values, run_id=run_id)
            self.table.clear()
            self.summary_var.set("")
            self.bar["value"] = 0
            self.status_var.set("Iniciando…")
            self.log_text.configure(state="normal")
            self.log_text.delete("1.0", "end")
            self.log_text.configure(state="disabled")
            self.btn_export.configure(state="disabled")
            self.btn_open.configure(state="disabled")
            self._append_log("info", f"{MODE_LABELS[mode]} iniciada (ID {run_id}).")
            self._set_running(True)
            threading.Thread(target=self._work, args=(mode, values, run_id), daemon=True).start()
        except Exception:
            self._release_operation()
            raise
        self.after(80, self._poll)

    def _work(self, mode: str, values: dict, run_id: str) -> None:
        """Roda numa thread: nunca toca na interface, só coloca mensagens na fila."""
        ctx = ExecutionContext(
            self.module.module_id,
            emit=lambda *a: self._queue.put(a),
            cancel_event=self._cancel,
            run_id=run_id,
        )
        try:
            result = self.module.preview(values, ctx) if mode == "preview" else self.module.execute(values, ctx)
        except CancelledError:
            result = Result(status=CANCELLED, summary="Execução cancelada pelo usuário.")
        except ToolkitError as exc:
            result = Result(status=FAILED, summary=str(exc), errors=1)
        except Exception as exc:  # noqa: BLE001
            get_logger().exception("Erro inesperado no módulo %s", self.module.module_id)
            result = Result(status=FAILED, summary=f"Erro inesperado: {exc}", errors=1)
        result.is_preview = mode == "preview"
        self._queue.put(("done", result))

    def _poll(self) -> None:
        try:
            while True:
                msg = self._queue.get_nowait()
                kind = msg[0]
                if kind == "log":
                    self._append_log(msg[1], msg[2])
                elif kind == "progress":
                    self._on_progress(msg[1], msg[2], msg[3])
                elif kind == "done":
                    self._finish(msg[1])
                    return
        except queue.Empty:
            pass
        if self._running:
            self.after(80, self._poll)

    def _on_progress(self, current: int, total: int, step: str) -> None:
        if total > 0:
            self.bar["value"] = min(100, current / total * 100)
        self.status_var.set(f"{step}… {current}/{total}" if step else f"{current}/{total}")

    def _append_log(self, level: str, message: str) -> None:
        now = datetime.now()
        self._events.append((now.strftime("%Y-%m-%d %H:%M:%S"), level, message))
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"[{now:%H:%M:%S}] {message}\n", level if level in ("warning", "error") else "info")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _finish(self, result: Result) -> None:
        if self._finished:
            return
        self._finished = True
        self._release_operation()
        self._set_running(False)
        self._last_result = result
        if self._exec_id is not None:
            self.history.finish(self._exec_id, result, self._events)
        prefix = "Pré-visualização: " if result.is_preview else ""
        icon = STATUS_ICONS.get(result.status, "")
        self.summary_var.set(f"{icon} {prefix}{STATUS_LABELS.get(result.status, result.status)} — {result.summary}")
        self.summary_label.configure(foreground=STATUS_COLORS.get(result.status, theme.TEXT))
        if result.status in (SUCCESS, PARTIAL):
            self.bar["value"] = 100
        status = "Concluído." if result.status in (SUCCESS, PARTIAL) else STATUS_LABELS.get(result.status, "")
        self.status_var.set(f"{status} · ID {self._run_id}" if self._run_id else status)
        self.table.set_rows(result.details)
        self._append_log("error" if result.status == FAILED else "info", result.summary)
        self.btn_export.configure(state="normal" if result.details else "disabled")
        self.btn_open.configure(state="normal" if result.output_files else "disabled")

    def _cancel_run(self) -> None:
        self._cancel.set()
        self.btn_cancel.configure(state="disabled")
        self.status_var.set("Cancelando…")

    # ---- saídas -------------------------------------------------------------------

    def _export(self) -> None:
        result = self._last_result
        if not result or not result.details:
            messagebox.showinfo("Exportar", "Não há resultado para exportar.")
            return
        path = filedialog.asksaveasfilename(
            title="Exportar resultado", defaultextension=".xlsx",
            initialfile=f"{self.module.module_id}_resultado.xlsx",
            filetypes=[("Excel", "*.xlsx"), ("CSV", "*.csv")])
        if not path:
            return
        try:
            export_rows(result.details, path)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Erro ao exportar", str(exc))
            return
        messagebox.showinfo("Exportado", f"Arquivo salvo em:\n{path}")

    def _open_output(self) -> None:
        if self._last_result and self._last_result.output_files:
            try:
                open_path(self._last_result.output_files[0])
            except OSError as exc:
                messagebox.showerror("Não foi possível abrir", str(exc))

    def refresh(self) -> None:
        self._refresh_fav()


# ---------------------------------------------------------------------------
# Página inicial
# ---------------------------------------------------------------------------

class HomePage(ttk.Frame):
    def __init__(self, parent, services: Services, registry, open_module):
        super().__init__(parent)
        self.history, self.registry, self._open = services.history, registry, open_module

        ttk.Label(self, text="Finance Toolkit", style="Title.TLabel").pack(anchor="w", padx=24, pady=(18, 0))
        ttk.Label(self, text="Utilitários locais para automatizar rotinas do setor financeiro. "
                             "Escolha uma ferramenta no menu à esquerda.", style="Muted.TLabel",
                  wraplength=820, justify="left").pack(anchor="w", padx=24, pady=(0, 12))

        cards = ttk.Frame(self)
        cards.pack(fill="x", padx=24)
        self._kpis: dict[str, ttk.Label] = {}
        for i, (key, title) in enumerate((("total", "Execuções"), ("ok", "Concluídas"),
                                          ("alerts", "Com alertas"), ("failed", "Com falhas"))):
            card = ttk.Frame(cards, style="Card.TFrame", padding=(16, 10))
            card.grid(row=0, column=i, sticky="ew", padx=(0, 10))
            cards.columnconfigure(i, weight=1)
            value = ttk.Label(card, text="0", style="KPI.TLabel")
            value.pack(anchor="w")
            ttk.Label(card, text=title, style="PanelMuted.TLabel").pack(anchor="w")
            self._kpis[key] = value

        ttk.Label(self, text="Favoritos", style="Section.TLabel").pack(anchor="w", padx=24, pady=(16, 4))
        self.fav_box = ttk.Frame(self)
        self.fav_box.pack(fill="x", padx=24)
        ttk.Label(self, text="Usados recentemente", style="Section.TLabel").pack(anchor="w", padx=24, pady=(12, 4))
        self.recent_box = ttk.Frame(self)
        self.recent_box.pack(fill="x", padx=24)

        ttk.Label(self, text="Últimas execuções", style="Section.TLabel").pack(anchor="w", padx=24, pady=(14, 4))
        columns = ("when", "module", "mode", "status", "summary")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", height=7)
        for col, title, width in (("when", "Data", 130), ("module", "Módulo", 230), ("mode", "Modo", 110),
                                  ("status", "Status", 130), ("summary", "Resumo", 520)):
            self.tree.heading(col, text=title)
            self.tree.column(col, width=width, anchor="w", stretch=col == "summary")
        self.tree.pack(fill="both", expand=True, padx=24, pady=(0, 6))
        self.roadmap = ttk.Label(self, text="", style="Muted.TLabel")
        self.roadmap.pack(anchor="w", padx=24, pady=(0, 14))

    def _fill_buttons(self, box, module_ids: list[str], empty_text: str) -> None:
        for child in box.winfo_children():
            child.destroy()
        if not module_ids:
            ttk.Label(box, text=empty_text, style="Muted.TLabel").pack(anchor="w")
            return
        for module_id in module_ids:
            ttk.Button(box, text=self.registry.name_of(module_id),
                       command=lambda i=module_id: self._open(i)).pack(side="left", padx=(0, 8), pady=2)

    def refresh(self) -> None:
        stats = self.history.stats()
        for key, label in self._kpis.items():
            label.configure(text=str(stats.get(key, 0)))
        self._fill_buttons(self.fav_box, [i for i in self.history.favorites() if self.registry.name_of(i) != i],
                           "Nenhum favorito ainda — use ☆ na página de uma ferramenta.")
        self._fill_buttons(self.recent_box, self.history.recent_modules(5), "Nenhuma ferramenta usada ainda.")
        self.tree.delete(*self.tree.get_children())
        for row in self.history.recent(8):
            self.tree.insert("", "end", values=(
                _short_date(row["started_at"]), row["module_name"], MODE_LABELS.get(row["mode"], row["mode"]),
                STATUS_LABELS.get(row["status"], row["status"]), row["summary"] or ""))
        self.roadmap.configure(
            text=f"{len(self.registry.modules())} ferramenta(s) disponíveis · "
                 f"{len(self.registry.planned())} planejadas no catálogo.")


# ---------------------------------------------------------------------------
# Histórico
# ---------------------------------------------------------------------------

class HistoryPage(ttk.Frame):
    def __init__(self, parent, services: Services):
        super().__init__(parent)
        self.history = services.history
        top = ttk.Frame(self)
        top.pack(fill="x", padx=24, pady=(18, 6))
        ttk.Label(top, text="Histórico de execuções", style="Title.TLabel").pack(side="left")
        ttk.Button(top, text="↻  Atualizar", command=self.refresh).pack(side="right")
        ttk.Label(self, text="Registra pré-visualizações e execuções (parâmetros, resultado e log). "
                             "Clique duas vezes em uma linha para ver os detalhes.",
                  style="Muted.TLabel").pack(anchor="w", padx=24, pady=(0, 8))

        columns = ("when", "module", "mode", "status", "processed", "warnings", "errors", "summary")
        self.tree = ttk.Treeview(self, columns=columns, show="headings")
        for col, title, width in (("when", "Data", 130), ("module", "Módulo", 220), ("mode", "Modo", 110),
                                  ("status", "Status", 120), ("processed", "Proc.", 60), ("warnings", "Alertas", 60),
                                  ("errors", "Erros", 50), ("summary", "Resumo", 460)):
            self.tree.heading(col, text=title)
            self.tree.column(col, width=width, anchor="w", stretch=col == "summary")
        self.tree.pack(fill="both", expand=True, padx=24, pady=(0, 18))
        self.tree.bind("<Double-1>", self._open_detail)
        self._ids: dict[str, int] = {}

    def refresh(self) -> None:
        self.tree.delete(*self.tree.get_children())
        self._ids = {}
        for row in self.history.recent(300):
            iid = self.tree.insert("", "end", values=(
                _short_date(row["started_at"]), row["module_name"], MODE_LABELS.get(row["mode"], row["mode"]),
                STATUS_LABELS.get(row["status"], row["status"]), row["processed"], row["warnings"], row["errors"],
                row["summary"] or ""))
            self._ids[iid] = row["id"]

    def _open_detail(self, _event) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        row = self.history.get(self._ids[selection[0]])
        if not row:
            return
        win = tk.Toplevel(self)
        win.title(f"Execução #{row['id']} — {row['module_name']}")
        win.geometry("900x620")
        win.configure(bg=theme.BG)
        notebook = ttk.Notebook(win)
        notebook.pack(fill="both", expand=True, padx=12, pady=12)

        summary_tab = ttk.Frame(notebook)
        notebook.add(summary_tab, text="Resumo")
        text = scrolledtext.ScrolledText(summary_tab, font=theme.MONO, bg=theme.FIELD, fg=theme.TEXT,
                                         relief="flat", padx=10, pady=8, wrap="word")
        text.pack(fill="both", expand=True)
        try:
            params = json.dumps(json.loads(row["params_json"] or "{}"), ensure_ascii=False, indent=2)
        except json.JSONDecodeError:
            params = row["params_json"] or ""
        lines = [
            f"Módulo: {row['module_name']} (v{row['module_version']})",
            f"ID da execução: {row['run_id'] or '-'}",
            f"Modo: {MODE_LABELS.get(row['mode'], row['mode'])}",
            f"Início: {row['started_at']}    Fim: {row['finished_at'] or '-'}",
            f"Status: {STATUS_LABELS.get(row['status'], row['status'])}",
            f"Processados: {row['processed']}   Alertas: {row['warnings']}   Erros: {row['errors']}",
            f"Resumo: {row['summary'] or ''}", "", "Arquivos de saída:",
            *[f"  {p}" for p in json.loads(row["output_files_json"] or "[]")], "",
            "Parâmetros:", params, "", "Log:",
            *[f"[{e['ts'][-8:]}] {e['message']}" for e in self.history.events(row["id"])],
        ]
        text.insert("1.0", "\n".join(lines))
        text.configure(state="disabled")

        details_tab = ttk.Frame(notebook, padding=8)
        notebook.add(details_tab, text="Detalhes")
        details = self.history.details(row["id"], limit=DETAILS_PREVIEW)
        total = int(row["details_count"] or 0) or len(details)
        table = ResultTable(details_tab)
        table.pack(fill="both", expand=True)
        table.set_rows(details)
        if total and not details:
            table.note.configure(
                text="Os detalhes foram registrados, mas não puderam ser lidos. "
                     "Verifique a pasta de dados."
            )
        elif total > len(details):
            table.note.configure(
                text=f"Mostrando {len(details)} de {total} linhas. "
                     "Use “Exportar detalhes” para ver tudo."
            )
        elif not total:
            table.note.configure(text="Esta execução não tem detalhes por linha/arquivo.")
        footer = ttk.Frame(details_tab)
        footer.pack(fill="x", pady=(8, 0))
        ttk.Label(footer, text=f"{total} linha(s) registrada(s)." if total else "",
                  style="Muted.TLabel").pack(side="left")
        ttk.Button(footer, text="Exportar detalhes…", command=lambda: self._export_details(row["id"]),
                   state="normal" if total else "disabled").pack(side="right")

    def _export_details(self, exec_id: int) -> None:
        rows = self.history.all_details(exec_id)
        if not rows:
            messagebox.showinfo("Exportar detalhes", "Esta execução não tem detalhes para exportar.",
                                parent=self)
            return
        path = filedialog.asksaveasfilename(
            parent=self, title="Exportar detalhes", defaultextension=".xlsx",
            initialfile=f"detalhes-{exec_id}.xlsx",
            filetypes=[("Excel", "*.xlsx"), ("CSV", "*.csv")])
        if not path:
            return
        try:
            export_rows(rows, path)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Erro ao exportar", str(exc), parent=self)
            return
        messagebox.showinfo("Exportado", f"Detalhes salvos em:\n{path}", parent=self)


# ---------------------------------------------------------------------------
# Utilitário planejado
# ---------------------------------------------------------------------------

class PlannedPage(ttk.Frame):
    def __init__(self, parent, planned):
        super().__init__(parent)
        ttk.Label(self, text=planned.name, style="Title.TLabel").pack(anchor="w", padx=24, pady=(18, 0))
        ttk.Label(self, text=f"{planned.category}  ·  em breve", style="Muted.TLabel").pack(anchor="w", padx=24)
        ttk.Label(self, text=planned.description, wraplength=820, justify="left").pack(anchor="w", padx=24, pady=(10, 14))
        card = ttk.Frame(self, style="Card.TFrame", padding=16)
        card.pack(anchor="w", padx=24)
        ttk.Label(card, text="🚧  Ainda não implementado", style="Panel.TLabel").pack(anchor="w")
        ttk.Label(card, text=f"Previsto na Fase {planned.phase} do plano de implementação.",
                  style="PanelMuted.TLabel").pack(anchor="w", pady=(4, 0))
