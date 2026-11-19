import os
import tempfile
import unittest
from pathlib import Path

from core.execution_context import ExecutionContext


class TempDirCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        os.environ["FINANCE_TOOLKIT_HOME"] = str(self.tmp / "_appdata")
        self.ctx = ExecutionContext("test")

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, rel: str, content: bytes | str = b"x") -> Path:
        p = self.tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, str):
            content = content.encode()
        p.write_bytes(content)
        return p
