import contextlib
import importlib.util
import io
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


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


if __name__ == '__main__':
    unittest.main()
