"""Package executable source and built UI only; never include local working data."""
import hashlib
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / 'outputs' / 'WorkspaceLSE-stand.tar.gz'


def package():
    files = {ROOT / '.dockerignore', ROOT / 'backend/manage.py', ROOT / 'backend/pyproject.toml', ROOT / 'backend/uv.lock'}
    for base in ('backend/apps', 'backend/config', 'backend/templates', 'infra/stand', 'frontend/dist'):
        files.update(path for path in (ROOT / base).rglob('*') if path.is_file()
                     and '__pycache__' not in path.parts and path.suffix not in ('.pyc', '.pyo')
                     and path.name != '.env' and not path.name.startswith('.env.'))
    if not (ROOT / 'frontend/dist/index.html').exists():
        raise SystemExit('Build frontend/dist before packaging.')
    OUTPUT.parent.mkdir(exist_ok=True)
    names = sorted(path.relative_to(ROOT).as_posix() for path in files)
    if any(part in name.split('/') for name in names for part in ('.runtime', '.stand-access', 'media', '.git', 'node_modules', '.venv', 'tests')):
        raise SystemExit('A private or development path was selected.')
    with tarfile.open(OUTPUT, 'w:gz') as archive:
        for name in names:
            archive.add(ROOT / name, arcname='WorkspaceLSE/' + name, recursive=False)
    with tarfile.open(OUTPUT, 'r:gz') as archive:
        assert len(archive.getnames()) == len(names)
        for member in archive.getmembers():
            assert member.isfile() and not member.name.startswith('/') and '..' not in member.name.split('/')
    digest = hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
    OUTPUT.with_suffix(OUTPUT.suffix + '.sha256').write_text(f'{digest}  {OUTPUT.name}\n', encoding='ascii')
    print(f'Package: {OUTPUT}; files: {len(names)}; bytes: {OUTPUT.stat().st_size}; SHA256: {digest}')


if __name__ == '__main__':
    package()
