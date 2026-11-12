"""Compatibility checks for the Windows updater; never use the working database."""
import os
import json
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'installation' / 'Update-FromGit.ps1'


@unittest.skipUnless(os.name == 'nt' and shutil.which('powershell.exe'), 'Windows PowerShell required')
class UpdatePreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='update-compat-', dir=ROOT / '.runtime')
        self.parent = Path(self.temp.name)
        self.root = self.parent / 'WorkspaceLSE'
        self.root.mkdir()
        self.addCleanup(self.temp.cleanup)
        for name, content in {
            'backend/.venv/Scripts/python.exe': '',
            '.runtime/postgresql/bin/pg_ctl.exe': '',
            '.runtime/postgresql-data/PG_VERSION': '17',
            '.runtime/postgresql-connection.json': '{}',
            'frontend/package-lock.json': '{}',
            'BUNDLE.txt': 'Revision: 62b2ad4\n',
        }.items():
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding='utf-8')

    def check(self):
        return subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                               '-File', str(SCRIPT), '-ProjectRoot', str(self.root), '-CheckOnly'],
                              capture_output=True, text=True)

    def test_original_embedded_postgres_without_dump_tools_is_supported_without_changes(self):
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('cold', result.stdout.lower())
        after = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(before, after)
        self.assertFalse((self.root / '.git').exists())

    def test_renamed_launcher_finds_installed_subfolder_from_bundle_parent(self):
        launcher = self.parent / 'Update-AIS.ps1'
        shutil.copy2(SCRIPT, launcher)
        result = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                                 '-File', str(launcher), '-CheckOnly'], cwd=ROOT,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Git setup required: True', result.stdout)
        self.assertIn('cold', result.stdout.lower())
        self.assertFalse((self.root / '.git').exists())


@unittest.skipUnless(os.name == 'nt' and (ROOT / '.runtime/postgresql/bin/pg_ctl.exe').exists(),
                     'Windows portable PostgreSQL required')
class ColdBackupTests(unittest.TestCase):
    def setUp(self):
        import psycopg
        self.pg = psycopg
        self.temp = tempfile.TemporaryDirectory(prefix='cold-backup-', dir=ROOT / '.runtime')
        self.root = Path(self.temp.name).resolve()
        assert self.root.parent == (ROOT / '.runtime').resolve()
        self.addCleanup(self.temp.cleanup)
        shutil.copytree(ROOT / '.runtime/postgresql', self.root / '.runtime/postgresql',
                        ignore=shutil.ignore_patterns('pg_dump.exe', 'pg_restore.exe'))
        (self.root / 'infra').mkdir()
        shutil.copy2(ROOT / 'infra/local.py', self.root / 'infra/local.py')
        self.data = self.root / '.runtime/postgresql-data'
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            self.port = sock.getsockname()[1]
        config = {'host': '127.0.0.1', 'port': self.port, 'dbname': 'ais_backup_check',
                  'user': 'backup_check', 'password': 'test-only-password', 'django_secret': 'test-only-key'}
        (self.root / '.runtime/postgresql-connection.json').write_text(json.dumps(config), encoding='utf-8')
        self.native('initdb', '-D', str(self.data), '-U', 'backup_check', '--locale=C', '--encoding=UTF8',
                    '--auth-local=trust', '--auth-host=trust')
        self.addCleanup(lambda: self.native('pg_ctl', '-D', str(self.data), 'stop', '-m', 'fast', '-w', check=False))
        result = subprocess.run([sys.executable, str(self.root / 'infra/local.py'), 'db-start'],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        with self.connect(self.port) as connection:
            connection.execute('CREATE TABLE backup_probe (value integer)')
            connection.execute('INSERT INTO backup_probe VALUES (42)')
        self.harness = self.root / 'backup-test.ps1'
        self.harness.write_text('''param([string]$Source,[string]$Root,[string]$Python,[switch]$FailCopy,[switch]$FailStop)
$ErrorActionPreference='Stop'
$tokens=$null; $errors=$null
$tree=[System.Management.Automation.Language.Parser]::ParseFile($Source,[ref]$tokens,[ref]$errors)
if($errors.Count){throw 'PowerShell parse failure'}
$functions=$tree.FindAll({param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -in @('Invoke-AisChecked','Backup-AisDatabase')},$true)
foreach($function in $functions){. ([scriptblock]::Create($function.Extent.Text))}
if($FailCopy){function Copy-Item { throw 'Simulated copy failure' }}
if($FailStop){
    $originalInvoke=${function:Invoke-AisChecked}
    function Invoke-AisChecked {
        param([string]$File,[string[]]$Arguments,[string]$Step)
        & $originalInvoke @PSBoundParameters
        if($Step -eq 'Stop database for cold backup'){throw 'Simulated stop failure after shutdown'}
    }
}
Backup-AisDatabase -Root $Root -Python $Python
''', encoding='utf-8')

    def native(self, program, *args, check=True):
        # Real files prevent a background postgres process retaining a pipe handle.
        with (self.root / f'{program}.log').open('wb') as output:
            result = subprocess.run([str(self.root / '.runtime/postgresql/bin' / (program + '.exe')), *args],
                                    stdout=output, stderr=subprocess.STDOUT)
        if check:
            self.assertEqual(result.returncode, 0, (self.root / f'{program}.log').read_text(errors='replace'))
        return result

    def connect(self, port):
        return self.pg.connect(host='127.0.0.1', port=port, dbname='ais_backup_check',
                               user='backup_check', connect_timeout=3)

    def backup(self, fail=False, fail_stop=False):
        command = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(self.harness),
                   '-Source', str(SCRIPT), '-Root', str(self.root), '-Python', sys.executable]
        return subprocess.run(command + (['-FailCopy'] if fail else []) + (['-FailStop'] if fail_stop else []),
                              capture_output=True, text=True)

    def test_minimal_runtime_backup_can_be_restored_and_original_database_restarts(self):
        result = self.backup()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        markers = list((self.root / 'backups').glob('*/BACKUP-COMPLETE.json'))
        self.assertEqual(len(markers), 1)
        metadata = json.loads(markers[0].read_text(encoding='utf-8-sig'))
        self.assertEqual(metadata['kind'], 'cold-postgresql-cluster')
        self.assertTrue(metadata['complete'])
        snapshot = markers[0].parent
        self.assertFalse((snapshot / 'postgresql-data/postmaster.pid').exists())
        self.assertEqual((snapshot / 'postgresql-connection.json').read_bytes(),
                         (self.root / '.runtime/postgresql-connection.json').read_bytes())
        with self.connect(self.port) as connection:
            self.assertEqual(connection.execute('SELECT value FROM backup_probe').fetchall(), [(42,)])
        restored = self.root / '.runtime/restored-data'
        shutil.copytree(snapshot / 'postgresql-data', restored)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            restored_port = sock.getsockname()[1]
        self.addCleanup(lambda: self.native('pg_ctl', '-D', str(restored), 'stop', '-m', 'fast', '-w', check=False))
        self.native('pg_ctl', '-D', str(restored), '-l', str(self.root / 'restored.log'),
                    '-o', f'-h 127.0.0.1 -p {restored_port}', 'start', '-w', '-t', '30')
        with self.connect(restored_port) as connection:
            self.assertEqual(connection.execute('SELECT value FROM backup_probe').fetchall(), [(42,)])

    def test_copy_failure_restarts_original_database_and_does_not_mark_a_backup_complete(self):
        result = self.backup(fail=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Simulated copy failure', result.stderr)
        self.assertEqual(list((self.root / 'backups').glob('*/BACKUP-COMPLETE.json')), [])
        with self.connect(self.port) as connection:
            self.assertEqual(connection.execute('SELECT value FROM backup_probe').fetchall(), [(42,)])

    def test_stop_reporting_failure_after_shutdown_still_restarts_original_database(self):
        result = self.backup(fail_stop=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Simulated stop failure after shutdown', result.stderr)
        self.assertEqual(list((self.root / 'backups').glob('*/BACKUP-COMPLETE.json')), [])
        with self.connect(self.port) as connection:
            self.assertEqual(connection.execute('SELECT value FROM backup_probe').fetchall(), [(42,)])


if __name__ == '__main__':
    unittest.main()
