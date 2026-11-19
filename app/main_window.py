"""Janela principal: menu lateral com busca, navegação entre páginas e tratamento global de erros."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from app import __version__, theme
from app.module_registry import ModuleRegistry
from app.pages import HistoryPage, HomePage, ModulePage, PlannedPage
from app.services import Services
from core.logging_service import get_logger
from core.normalizers import strip_accents


def _norm(text: str) -> str:
    return strip_accents(text).casefold().strip()


class MainWindow(tk.Tk):
    def __init__(self, services: Services, registry: ModuleRegistry):
        super().__init__()
        self.services, self.registry = services, registry
        self.title("Finance Toolkit")
        self.geometry("1220x780")
        self.minsize(1000, 660)
        theme.apply_theme(self)

        self._pages: dict[str, ttk.Frame] = {}
        self._current_key: str | None = None
        self._build_sidebar()
        self.content = ttk.Frame(self)
        self.content.pack(side="left", fill="both", expand=True)
        self.show_home()

    # ---- erros inesperados em callbacks da interface -----------------------------

    def report_callback_exception(self, exc, val, tb):  # noqa: D401
        get_logger().error("Erro inesperado na interface", exc_info=(exc, val, tb))
        messagebox.showerror("Erro inesperado", f"{val}\n\nO detalhe foi gravado no arquivo de log.")

    # ---- menu lateral ---------------------------------------------------------------

    def _build_sidebar(self) -> None:
        side = ttk.Frame(self, style="Panel.TFrame", width=300)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        ttk.Label(side, text="💼 Finance Toolkit", style="Panel.TLabel", font=("Segoe UI", 13, "bold")).pack(
            anchor="w", padx=16, pady=(16, 8))
        nav = ttk.Frame(side, style="Panel.TFrame")
        nav.pack(fill="x", padx=12)
        ttk.Button(nav, text="🏠  Início", command=self.show_home).pack(side="left", padx=(0, 6))
        ttk.Button(nav, text="🕘  Histórico", command=self.show_history).pack(side="left")

        self.search_var = tk.StringVar()
        ttk.Entry(side, textvariable=self.search_var).pack(fill="x", padx=16, pady=(12, 6))
        self.search_var.trace_add("write", lambda *_: self._fill_tree())
        ttk.Label(side, text="Pesquisar por nome ou finalidade", style="PanelMuted.TLabel").pack(anchor="w", padx=16)

        self.tree = ttk.Treeview(side, show="tree", selectmode="browse")
        self.tree.pack(fill="both", expand=True, padx=12, pady=10)
        self.tree.tag_configure("category", foreground=theme.ACCENT, font=theme.FONT_BOLD)
        self.tree.tag_configure("planned", foreground=theme.MUTED)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        ttk.Label(side, text=f"v{__version__}", style="PanelMuted.TLabel").pack(anchor="w", padx=16, pady=(0, 10))
        self._fill_tree()

    def _matches(self, query: str, *texts: str) -> bool:
        return not query or any(query in _norm(t) for t in texts)

    def _fill_tree(self) -> None:
        query = _norm(self.search_var.get())
        self.tree.delete(*self.tree.get_children())
        for category in self.registry.categories():
            modules = [m for m in self.registry.modules()
                       if m.category == category and self._matches(query, m.name, m.description)]
            planned = [p for p in self.registry.planned()
                       if p.category == category and self._matches(query, p.name, p.description)]
            if not modules and not planned:
                continue
            cat_id = f"cat:{category}"
            self.tree.insert("", "end", iid=cat_id, text=category.upper(), open=True, tags=("category",))
            for m in modules:
                self.tree.insert(cat_id, "end", iid=m.module_id, text="  " + m.name)
            for p in planned:
                self.tree.insert(cat_id, "end", iid=p.module_id, text="  " + p.name + "  · em breve", tags=("planned",))

    def _on_select(self, _event) -> None:
        selection = self.tree.selection()
        if selection and not selection[0].startswith("cat:"):
            self.show_module(selection[0])

    # ---- navegação -------------------------------------------------------------------

    def _show(self, key: str, factory) -> None:
        if key == self._current_key:
            page = self._pages[key]
        else:
            if self._current_key is not None:
                self._pages[self._current_key].pack_forget()
            if key not in self._pages:
                self._pages[key] = factory(self.content)
            page = self._pages[key]
            page.pack(fill="both", expand=True)
            self._current_key = key
        if hasattr(page, "refresh"):
            page.refresh()

    def _clear_selection(self) -> None:
        selection = self.tree.selection()
        if selection:
            self.tree.selection_remove(*selection)

    def show_home(self) -> None:
        self._clear_selection()
        self._show("home", lambda p: HomePage(p, self.services, self.registry, self.show_module))

    def show_history(self) -> None:
        self._clear_selection()
        self._show("history", lambda p: HistoryPage(p, self.services))

    def show_module(self, module_id: str) -> None:
        module = self.registry.get(module_id)
        if module is not None:
            self._show(f"mod:{module_id}", lambda p: ModulePage(p, module, self.services))
        else:
            planned = self.registry.get_planned(module_id)
            if planned is None:
                return
            self._show(f"planned:{module_id}", lambda p: PlannedPage(p, planned))
        if self.tree.exists(module_id) and module_id not in self.tree.selection():
            self.tree.selection_set(module_id)
            self.tree.see(module_id)
