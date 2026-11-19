"""Tema escuro do aplicativo."""
from tkinter import ttk

BG = "#1E2228"
PANEL = "#252B34"
ACCENT = "#00C48C"
ACCENT_DARK = "#00A87A"
TEXT = "#E8EAF0"
MUTED = "#8B93A1"
ERR = "#FF5C5C"
WARN = "#E0B84D"
FIELD = "#2D3440"
BORDER = "#3A4252"

FONT = ("Segoe UI", 10)
FONT_BOLD = ("Segoe UI", 10, "bold")
FONT_TITLE = ("Segoe UI", 18, "bold")
FONT_KPI = ("Segoe UI", 22, "bold")
MONO = ("Consolas", 9)


def apply_theme(root) -> None:
    root.configure(bg=BG)
    s = ttk.Style(root)
    s.theme_use("clam")

    s.configure(".", background=BG, foreground=TEXT, font=FONT, bordercolor=BORDER,
                lightcolor=BG, darkcolor=BG, troughcolor=FIELD, fieldbackground=FIELD)
    for name, bg in (("TFrame", BG), ("Panel.TFrame", PANEL), ("Card.TFrame", PANEL)):
        s.configure(name, background=bg)
    s.configure("TLabel", background=BG, foreground=TEXT)
    s.configure("Muted.TLabel", background=BG, foreground=MUTED)
    s.configure("Panel.TLabel", background=PANEL, foreground=TEXT, font=FONT_BOLD)
    s.configure("PanelMuted.TLabel", background=PANEL, foreground=MUTED)
    s.configure("Title.TLabel", background=BG, foreground=ACCENT, font=FONT_TITLE)
    s.configure("KPI.TLabel", background=PANEL, foreground=ACCENT, font=FONT_KPI)
    s.configure("Section.TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 11, "bold"))

    s.configure("TButton", background=BORDER, foreground=TEXT, padding=(12, 7), borderwidth=0,
                focusthickness=0, focuscolor=BORDER)
    s.map("TButton", background=[("disabled", PANEL), ("active", "#46506A")],
          foreground=[("disabled", MUTED)])
    s.configure("Accent.TButton", background=ACCENT, foreground=BG, font=FONT_BOLD)
    s.map("Accent.TButton", background=[("disabled", BORDER), ("active", ACCENT_DARK)],
          foreground=[("disabled", MUTED), ("active", BG)])
    s.configure("Danger.TButton", background=ERR, foreground=BG, font=FONT_BOLD)
    s.map("Danger.TButton", background=[("disabled", BORDER), ("active", "#CC4848")],
          foreground=[("disabled", MUTED), ("active", BG)])
    s.configure("Ghost.TButton", background=BG, foreground=MUTED, padding=(8, 4))
    s.map("Ghost.TButton", foreground=[("active", ACCENT)], background=[("active", BG)])

    s.configure("TEntry", fieldbackground=FIELD, foreground=TEXT, insertcolor=TEXT, padding=5, borderwidth=0)
    s.configure("TCombobox", fieldbackground=FIELD, background=BORDER, foreground=TEXT, arrowcolor=TEXT,
                bordercolor=BORDER, lightcolor=FIELD, darkcolor=FIELD, padding=4)
    s.map("TCombobox", fieldbackground=[("readonly", FIELD)], foreground=[("readonly", TEXT)])
    root.option_add("*TCombobox*Listbox.background", FIELD)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
    root.option_add("*TCombobox*Listbox.selectForeground", BG)

    s.configure("TCheckbutton", background=BG, foreground=TEXT)
    s.configure("Panel.TCheckbutton", background=PANEL, foreground=TEXT)
    for name in ("TCheckbutton", "Panel.TCheckbutton"):
        s.map(name, indicatorcolor=[("selected", ACCENT), ("!selected", FIELD)],
              background=[("active", PANEL if name.startswith("Panel") else BG)])

    s.configure("Treeview", background=FIELD, fieldbackground=FIELD, foreground=TEXT, rowheight=24, borderwidth=0)
    s.map("Treeview", background=[("selected", ACCENT)], foreground=[("selected", BG)])
    s.configure("Treeview.Heading", background=BORDER, foreground=TEXT, relief="flat", font=FONT_BOLD, padding=4)
    s.map("Treeview.Heading", background=[("active", "#46506A")])

    s.configure("TNotebook", background=BG, borderwidth=0)
    s.configure("TNotebook.Tab", background=PANEL, foreground=MUTED, padding=(14, 6), borderwidth=0)
    s.map("TNotebook.Tab", background=[("selected", FIELD)], foreground=[("selected", ACCENT)])

    s.configure("TProgressbar", troughcolor=FIELD, background=ACCENT, thickness=8, borderwidth=0)
    s.configure("TScrollbar", background=BORDER, troughcolor=FIELD, arrowcolor=TEXT, borderwidth=0)
    s.configure("TPanedwindow", background=BG)
    s.configure("Sash", sashthickness=6, background=BG)
