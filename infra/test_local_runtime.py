import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import MagicMock, patch


class PostgreSQLDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        source = Path(__file__).with_name('local.py')
        spec = importlib.util.spec_from_file_location('local_runtime_test', source)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        runtime = source.parent.parent / '.runtime'
        runtime.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='pg-output-test-', dir=runtime)
        self.addCleanup(self.temp.cleanup)
        self.module.RUNTIME = Path(self.temp.name)

    def test_failure_prints_native_error_and_retains_log(self):
        result = subprocess.CompletedProcess(['initdb'], 1, b'creating directory...\n', b'Permission denied\n')
        output, errors = io.StringIO(), io.StringIO()
        def native_output(*args, **kwargs):
            kwargs['stdout'].write(result.stdout + result.stderr)
            return result
        with patch.object(self.module.subprocess, 'run', side_effect=native_output):
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
                with self.assertRaises(SystemExit):
                    self.module.run_pg('initdb', '--pwfile=not-logged')
        self.assertIn('Permission denied', errors.getvalue())
        self.assertIn('creating directory', errors.getvalue())
        log = (self.module.RUNTIME / 'postgresql-initdb.log').read_text(encoding='utf-8')
        self.assertIn('Permission denied', log)
        self.assertNotIn('not-logged', log)

    def test_expected_nonzero_status_remains_a_result(self):
        result = subprocess.CompletedProcess(['pg_ctl'], 3, b'no server running\n', b'')
        def native_output(*args, **kwargs):
            kwargs['stdout'].write(result.stdout)
            return result
        with patch.object(self.module.subprocess, 'run', side_effect=native_output):
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(self.module.run_pg('pg_ctl', 'status', check=False).returncode, 3)

    def test_success_shows_native_output(self):
        result = subprocess.CompletedProcess(['pg_ctl'], 0, b'server started\n', b'')
        output = io.StringIO()
        def native_output(*args, **kwargs):
            kwargs['stdout'].write(result.stdout)
            return result
        with patch.object(self.module.subprocess, 'run', side_effect=native_output):
            with contextlib.redirect_stdout(output):
                self.assertEqual(self.module.run_pg('pg_ctl', 'start').returncode, 0)
        self.assertIn('server started', output.getvalue())

    def test_db_start_ignores_web_and_journal_settings_in_database_connection(self):
        self.module.DATA = self.module.RUNTIME / 'data'
        self.module.DATA.mkdir()
        (self.module.DATA / 'PG_VERSION').write_text('17', encoding='utf-8')
        self.module.CONNECTION = self.module.RUNTIME / 'connection.json'
        self.module.CONNECTION.write_text(json.dumps({
            'host': '127.0.0.1', 'port': 55432, 'dbname': 'test_database',
            'user': 'test_user', 'password': 'test-only-password', 'django_secret': 'test-only-secret',
            'web_hosts': ['127.0.0.1', '10.10.0.2'], 'journal_source': {'gid': '0'},
        }), encoding='utf-8')
        connection = MagicMock()
        connection.__enter__.return_value.execute.return_value.fetchone.return_value = (1,)
        with patch.object(self.module, 'run_pg', return_value=subprocess.CompletedProcess([], 0)):
            with patch('psycopg.connect', return_value=connection) as connect:
                with contextlib.redirect_stdout(io.StringIO()):
                    self.module.db_start()
        connect.assert_called_once_with(host='127.0.0.1', port=55432, dbname='postgres',
                                        user='test_user', password='test-only-password',
                                        autocommit=True, connect_timeout=3)


if __name__ == '__main__':
    unittest.main()
