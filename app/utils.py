from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def open_path(path) -> None:
    """Abre um arquivo ou pasta no explorador do sistema."""
    p = Path(path)
    target = p if p.is_dir() else p.parent
    if sys.platform.startswith("win"):
        os.startfile(str(target))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(target)])
    else:
        subprocess.Popen(["xdg-open", str(target)])
