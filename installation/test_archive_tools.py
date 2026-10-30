import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile


SCRIPT = Path(__file__).with_name('archive_tools.py')


class ArchiveToolsTests(unittest.TestCase):
    def setUp(self):
        runtime = SCRIPT.parent.parent / '.runtime'
        runtime.mkdir(exist_ok=True)
        self.root = Path(tempfile.mkdtemp(prefix='archive-test-', dir=runtime))
        self.runtime = runtime.resolve()
        self.addCleanup(self.cleanup_root)

    def cleanup_root(self):
        target = self.root.resolve()
        self.assertEqual(target.parent, self.runtime)
        native = str(target)
        if os.name == 'nt':
            native = '\\\\?\\' + native
        shutil.rmtree(native)

    def run_tool(self, command, source, destination):
        environment = os.environ.copy()
        environment['PATH'] = ''  # No tar, gzip or xz executable can be found.
        result = subprocess.run(
            [sys.executable, str(SCRIPT), command, str(source), str(destination)],
            env=environment, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_postgresql_nested_xz_archive_without_external_programs(self):
        contents = io.BytesIO()
        with tarfile.open(fileobj=contents, mode='w:xz') as archive:
            for name in ('bin', 'share', 'share/tsearch_data'):
                directory = tarfile.TarInfo(name)
                directory.type = tarfile.DIRTYPE
                archive.addfile(directory)
            item = tarfile.TarInfo('bin/postgres.exe')
            payload = b'postgres fixture'
            item.size = len(payload)
            archive.addfile(item, io.BytesIO(payload))
        source = self.root / 'postgresql.jar'
        with zipfile.ZipFile(source, 'w') as archive:
            archive.writestr('postgres-windows-x86_64.txz', contents.getvalue())
        destination = self.root / 'postgresql'
        self.run_tool('postgres', source, destination)
        self.assertEqual((destination / 'bin/postgres.exe').read_bytes(), b'postgres fixture')

    def test_npm_cache_extracts_long_hash_paths_without_external_programs(self):
        source = self.root / 'cache.tgz'
        relative = '_cacache/content-v2/sha512/00/ff/' + 'a' * 124
        with tarfile.open(source, 'w:gz') as archive:
            item = tarfile.TarInfo(relative)
            item.size = 5
            archive.addfile(item, io.BytesIO(b'cache'))
        destination = self.root / ('long-install-directory-' * 5)
        target = str(destination / relative)
        self.assertGreater(len(target), 260)
        self.run_tool('extract', source, destination)
        if os.name == 'nt':
            target = '\\\\?\\' + target
        with open(target, 'rb') as result:
            self.assertEqual(result.read(), b'cache')

    def test_pack_cache_includes_only_content_cache(self):
        source = self.root / 'npm'
        (source / '_cacache').mkdir(parents=True)
        (source / '_cacache/item').write_bytes(b'cache')
        (source / 'not-for-distribution.log').write_text('excluded')
        output = self.root / 'cache.tgz'
        self.run_tool('pack-cache', source, output)
        with tarfile.open(output, 'r:gz') as archive:
            self.assertEqual(sorted(archive.getnames()), ['_cacache', '_cacache/item'])


if __name__ == '__main__':
    unittest.main()
