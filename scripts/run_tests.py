"""Executa a suíte de testes com medição de cobertura.

Uso:
    python scripts/run_tests.py

Requer as dependências de desenvolvimento:
    python -m pip install -r requirements-dev.txt
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    try:
        import coverage
    except ImportError:
        print(
            "Cobertura indisponível. Instale as dependências de desenvolvimento:\n"
            "  python -m pip install -r requirements-dev.txt",
            file=sys.stderr,
        )
        return 2

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    cov = coverage.Coverage(config_file=str(ROOT / ".coveragerc"))
    cov.start()
    try:
        suite = unittest.defaultTestLoader.discover(
            str(ROOT / "tests"), top_level_dir=str(ROOT)
        )
        result = unittest.TextTestRunner(verbosity=1).run(suite)
    finally:
        cov.stop()
        cov.save()

    total = cov.report(show_missing=True)
    print(f"\nCobertura de linhas: {total:.1f}%")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
