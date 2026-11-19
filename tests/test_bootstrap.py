import os
import unittest
from unittest import mock

from app import bootstrap
from core.paths import app_data_dir
from tests.helpers import TempDirCase


class BootstrapTests(unittest.TestCase):
    def test_falha_de_pasta_mostra_mensagem_e_sai(self):
        with mock.patch.object(bootstrap, "setup_logging") as setup, \
                mock.patch.object(bootstrap, "db_path", side_effect=OSError("sem permissão")), \
                mock.patch.object(bootstrap, "_show_message") as show:
            with self.assertRaises(SystemExit) as ctx:
                bootstrap.run()

        self.assertEqual(ctx.exception.code, 1)
        setup.return_value.exception.assert_called_once()
        show.assert_called_once()
        self.assertIn("pasta de dados", show.call_args.args[1])

    def test_falha_inesperada_mostra_mensagem(self):
        with mock.patch.object(bootstrap, "setup_logging") as setup, \
                mock.patch.object(bootstrap, "db_path", side_effect=RuntimeError("falha inesperada")), \
                mock.patch.object(bootstrap, "_show_message") as show:
            with self.assertRaises(SystemExit):
                bootstrap.run()

        setup.return_value.exception.assert_called_once()
        show.assert_called_once()
        self.assertIn("falha inesperada", show.call_args.args[1])


class DataFolderTests(TempDirCase):
    def test_pasta_de_dados_aponta_para_arquivo(self):
        blocker = self.tmp / "bloqueio"
        blocker.write_text("x")
        old = os.environ["FINANCE_TOOLKIT_HOME"]
        os.environ["FINANCE_TOOLKIT_HOME"] = str(blocker)
        try:
            with self.assertRaises(OSError):
                app_data_dir()
        finally:
            os.environ["FINANCE_TOOLKIT_HOME"] = old
