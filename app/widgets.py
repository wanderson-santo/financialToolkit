"""Componentes reutilizáveis: formulário gerado por ParamSpec, tabela de resultado e área rolável."""
from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from app import theme
from core.base_module import ParamSpec
from core.normalizers import strip_accents
from core.spreadsheet_service import list_columns


def _norm(text: str) -> str:
    return strip_accents(str(text)).casefold().strip()


def match_hint(cols: list[str], hint: str, exact_only: bool = False) -> str:
    """Primeira coluna cujo nome é igual (ou contém) a dica, ignorando acento e caixa."""
    h = _norm(hint)
    if not h:
        return ""
    for c in cols:
        if _norm(c) == h:
            return c
    if not exact_only:
        for c in cols:
            if h in _norm(c):
                return c
    return ""


class ScrollFrame(ttk.Frame):
    """Área com rolagem vertical (roda do mouse incluída)."""

    def __init__(self, parent, bg: str = theme.PANEL, style: str = "Panel.TFrame"):
        super().__init__(parent)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas, style=style)
        self._window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._window, width=e.width))
        self.bind_all("<MouseWheel>", self._on_wheel, add="+")

    def _on_wheel(self, event) -> None:
        widget = self.winfo_containing(*self.winfo_pointerxy())
        if widget is None or isinstance(widget, (tk.Text, tk.Listbox)):
            return
        while widget is not None:
            if widget is self:
                self.canvas.yview_scroll(int(-event.delta / 120) or (-1 if event.delta > 0 else 1), "units")
                return
            widget = widget.master


class ResultTable(ttk.Frame):
    """Tabela somente leitura para exibir `Result.details`."""

    MAX_ROWS = 1000

    def __init__(self, parent):
        super().__init__(parent)
        self.tree = ttk.Treeview(self, show="headings", selectmode="extended")
        vs = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        hs = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vs.grid(row=0, column=1, sticky="ns")
        hs.grid(row=1, column=0, sticky="ew")
        self.note = ttk.Label(self, text="", style="Muted.TLabel")
        self.note.grid(row=2, column=0, columnspan=2, sticky="w")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

    def clear(self) -> None:
        self.tree.delete(*self.tree.get_children())
        self.tree["columns"] = ()
        self.note.configure(text="")

    def set_rows(self, rows: list[dict]) -> None:
        self.clear()
        if not rows:
            return
        names: list[str] = []
        for row in rows[:100]:
            for key in row:
                if key not in names:
                    names.append(key)
        ids = [f"c{i}" for i in range(len(names))]
        self.tree["columns"] = ids
        for cid, name in zip(ids, names):
            sample = [len(str(name))] + [len(str(r.get(name, ""))) for r in rows[:50]]
            self.tree.heading(cid, text=name)
            self.tree.column(cid, width=min(max(sample) * 8 + 24, 420), minwidth=60, anchor="w", stretch=False)
        for row in rows[: self.MAX_ROWS]:
            self.tree.insert("", "end", values=[str(row.get(n, ""))[:300] for n in names])
        if len(rows) > self.MAX_ROWS:
            self.note.configure(
                text=f"Mostrando {self.MAX_ROWS} de {len(rows)} linhas. Use “Exportar resultado” para ver tudo."
            )


class ParamForm(ttk.Frame):
    """Monta o formulário de um módulo a partir da lista de ParamSpec."""

    def __init__(self, parent, params: list[ParamSpec]):
        super().__init__(parent, style="Panel.TFrame", padding=(14, 6, 14, 14))
        self.params = params
        self._vars: dict[str, tk.Variable] = {}
        self._texts: dict[str, tk.Text] = {}
        self._lists: dict[str, tk.Listbox] = {}
        self._combos: dict[str, ttk.Combobox] = {}
        self._pending: dict[str, list[str]] = {}
        self._loaded: dict[str, tuple] = {}
        self.columnconfigure(0, weight=1)
        row = 0
        for spec in params:
            row = self._add_field(spec, row)

    # ---- construção ---------------------------------------------------------

    def _add_field(self, spec: ParamSpec, row: int) -> int:
        if spec.kind == "bool":
            var = tk.BooleanVar(value=bool(spec.default))
            self._vars[spec.key] = var
            ttk.Checkbutton(self, text=spec.label, variable=var, style="Panel.TCheckbutton").grid(
                row=row, column=0, sticky="w", pady=(10, 0))
            row += 1
        else:
            star = " *" if spec.required else ""
            ttk.Label(self, text=spec.label + star, style="Panel.TLabel").grid(
                row=row, column=0, sticky="w", pady=(10, 2))
            row += 1
            self._build_input(spec).grid(row=row, column=0, sticky="ew")
            row += 1
        if spec.help:
            ttk.Label(self, text=spec.help, style="PanelMuted.TLabel", wraplength=700, justify="left").grid(
                row=row, column=0, sticky="w", pady=(2, 0))
            row += 1
        return row

    def _build_input(self, spec: ParamSpec):
        key = spec.key
        if spec.kind in ("file", "folder"):
            var = tk.StringVar(value=spec.default or "")
            self._vars[key] = var
            box = ttk.Frame(self, style="Panel.TFrame")
            box.columnconfigure(0, weight=1)
            entry = ttk.Entry(box, textvariable=var)
            entry.grid(row=0, column=0, sticky="ew")
            ttk.Button(box, text="Procurar…", command=lambda s=spec: self._browse(s)).grid(
                row=0, column=1, padx=(8, 0))
            if spec.kind == "file":
                entry.bind("<FocusOut>", lambda e: self.refresh_sources())
                entry.bind("<Return>", lambda e: self.refresh_sources(silent=False))
            return box
        if spec.kind == "text":
            var = tk.StringVar(value=spec.default or "")
            self._vars[key] = var
            entry = ttk.Entry(self, textvariable=var)
            if key == "sheet":
                entry.bind("<FocusOut>", lambda e: self.refresh_sources())
            return entry
        if spec.kind == "multiline":
            text = tk.Text(self, height=spec.height, wrap="word", bg=theme.FIELD, fg=theme.TEXT,
                           insertbackground=theme.TEXT, relief="flat", font=theme.MONO, padx=6, pady=4,
                           highlightthickness=1, highlightbackground=theme.BORDER, highlightcolor=theme.ACCENT)
            text.insert("1.0", spec.default or "")
            self._texts[key] = text
            return text
        if spec.kind == "choice":
            choices = spec.choices or []
            var = tk.StringVar(value=spec.default if spec.default in choices else (choices[0] if choices else ""))
            self._vars[key] = var
            return ttk.Combobox(self, textvariable=var, values=choices, state="readonly")
        if spec.kind == "column":
            var = tk.StringVar(value="")
            self._vars[key] = var
            combo = ttk.Combobox(self, textvariable=var, values=[], state="readonly")
            self._combos[key] = combo
            return combo
        if spec.kind == "columns":
            box = ttk.Frame(self, style="Panel.TFrame")
            box.columnconfigure(0, weight=1)
            lb = tk.Listbox(box, selectmode="extended", exportselection=False, height=spec.height,
                            bg=theme.FIELD, fg=theme.TEXT, selectbackground=theme.ACCENT,
                            selectforeground=theme.BG, relief="flat", highlightthickness=1,
                            highlightbackground=theme.BORDER, activestyle="none", font=theme.FONT)
            sb = ttk.Scrollbar(box, orient="vertical", command=lb.yview)
            lb.configure(yscrollcommand=sb.set)
            lb.grid(row=0, column=0, sticky="ew")
            sb.grid(row=0, column=1, sticky="ns")
            self._lists[key] = lb
            return box
        raise ValueError(f"Tipo de parâmetro desconhecido: {spec.kind}")

    # ---- valores --------------------------------------------------------------

    def get_values(self) -> dict:
        values: dict = {}
        for spec in self.params:
            key = spec.key
            if spec.kind == "multiline":
                values[key] = self._texts[key].get("1.0", "end-1c")
            elif spec.kind == "columns":
                lb = self._lists[key]
                values[key] = [lb.get(i) for i in lb.curselection()]
            elif spec.kind == "bool":
                values[key] = bool(self._vars[key].get())
            else:
                values[key] = str(self._vars[key].get()).strip()
        return values

    def set_values(self, values: dict) -> None:
        for spec in self.params:
            if spec.key not in values:
                continue
            value = values[spec.key]
            if spec.kind == "multiline":
                self._texts[spec.key].delete("1.0", "end")
                self._texts[spec.key].insert("1.0", value or "")
            elif spec.kind == "columns":
                self._pending[spec.key] = list(value or [])
            elif spec.kind == "bool":
                self._vars[spec.key].set(bool(value))
            elif spec.kind == "choice":
                if value in (spec.choices or []):
                    self._vars[spec.key].set(value)
            else:
                self._vars[spec.key].set(value or "")

    def load(self, values: dict) -> None:
        """Aplica valores salvos e carrega as colunas das planilhas já escolhidas."""
        self.set_values(values)
        self.refresh_sources()

    # ---- colunas das planilhas ------------------------------------------------

    def refresh_sources(self, silent: bool = True) -> None:
        sheet = self._vars["sheet"].get().strip() if "sheet" in self._vars else ""
        cache: dict[tuple, list[str] | None] = {}
        for spec in self.params:
            if spec.kind not in ("column", "columns") or not spec.source:
                continue
            path = str(self._vars[spec.source].get()).strip()
            if not path or not os.path.isfile(path):
                continue
            sig = (path, sheet)
            if sig not in cache:
                try:
                    cache[sig] = list_columns(path, sheet or None)
                except Exception as exc:  # noqa: BLE001 - mostra qualquer falha de leitura ao usuário
                    cache[sig] = None
                    if not silent:
                        messagebox.showerror("Não foi possível ler a planilha", str(exc))
            cols = cache[sig]
            if cols is None or self._loaded.get(spec.key) == (sig, tuple(cols)):
                continue
            self._loaded[spec.key] = (sig, tuple(cols))
            self._apply_columns(spec, cols)

    def _apply_columns(self, spec: ParamSpec, cols: list[str]) -> None:
        hint = spec.default if isinstance(spec.default, str) else ""
        if spec.kind == "column":
            self._combos[spec.key]["values"] = ([] if spec.required else [""]) + cols
            var = self._vars[spec.key]
            if var.get() not in cols:
                var.set(match_hint(cols, hint))
            return
        lb = self._lists[spec.key]
        previous = {lb.get(i) for i in lb.curselection()}
        lb.delete(0, "end")
        for col in cols:
            lb.insert("end", col)
        if spec.key in self._pending:
            selected = set(self._pending.pop(spec.key))
        elif previous:
            selected = previous
        else:
            exact = match_hint(cols, hint, exact_only=True)
            selected = {exact} if exact else set()
        for i, col in enumerate(cols):
            if col in selected:
                lb.selection_set(i)

    # ---- diálogos ---------------------------------------------------------------

    def _browse(self, spec: ParamSpec) -> None:
        current = str(self._vars[spec.key].get()).strip()
        initial = current if os.path.isdir(current) else (os.path.dirname(current) if current else "")
        options = {"initialdir": initial} if initial and os.path.isdir(initial) else {}
        if spec.kind == "file":
            path = filedialog.askopenfilename(
                title=spec.label, filetypes=spec.filetypes or [("Todos os arquivos", "*.*")], **options)
        else:
            path = filedialog.askdirectory(title=spec.label, mustexist=True, **options)
        if path:
            self._vars[spec.key].set(path)
            if spec.kind == "file":
                self.refresh_sources(silent=False)
