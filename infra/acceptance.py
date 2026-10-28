"""Disposable-data acceptance runtime. No reset/drop or working-database mode."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / '.runtime/cross-role-acceptance/state.json'
CONFIG = ROOT / '.runtime/postgresql-connection.json'
sys.path.insert(0, str(ROOT))


def checked_database_name(value: str) -> str:
    if not re.fullmatch(r'ais_lse_acceptance_[a-z0-9_]{1,43}', value):
        raise ValueError('Only a fresh named ais_lse_acceptance_* database is allowed')
    return value


def runtime_env(config: dict, state: dict) -> dict:
    if config['host'] != '127.0.0.1':
        raise ValueError('Acceptance database must be on loopback')
    env = os.environ.copy()
    env.update(PGHOST='127.0.0.1', PGPORT=str(config['port']), PGDATABASE=checked_database_name(state['database']),
        PGUSER=config['user'], PGPASSWORD=config['password'], DJANGO_SECRET_KEY=state['django_secret'],
        DJANGO_SETTINGS_MODULE='config.settings', DJANGO_DEBUG='1', DJANGO_ALLOWED_HOSTS='127.0.0.1,localhost',
        CSRF_TRUSTED_ORIGINS='http://127.0.0.1:8001', COOKIE_SECURE='0', PYTHONUTF8='1',
        AIS_JOURNAL_GOOGLE_ID='', AIS_JOURNAL_GOOGLE_GID='', AIS_JOURNAL_GOOGLE_SHEET_NAME='')
    return env


def checked_state_path(path):
    path = Path(path).resolve()
    if not path.is_relative_to(ROOT / '.runtime') or not path.parent.name.startswith('cross-role-acceptance'):
        raise ValueError('Acceptance state belongs in a dedicated .runtime/cross-role-acceptance* directory')
    return path


def apply_acceptance_settings(settings, state):
    settings.MEDIA_ROOT = Path(state['media'])
    # Browser cookies are not port-scoped: do not replace the live :5173/:8000 session.
    settings.SESSION_COOKIE_NAME = 'acceptance_sessionid'
    settings.CSRF_COOKIE_NAME = 'acceptance_csrftoken'


def setup_django(config, state):
    import django
    from django.conf import settings
    if settings.configured:
        raise RuntimeError('Acceptance must start in a fresh process, not replace an existing Django environment')
    os.environ.update(runtime_env(config, state))
    sys.path.insert(0, str(ROOT / 'backend'))
    django.setup()
    apply_acceptance_settings(settings, state)


def prepare(*, state_path=STATE, config_path=CONFIG):
    state_path = Path(state_path)
    if state_path.exists():
        raise FileExistsError('Acceptance state already exists; never overwrite it')
    state_path = checked_state_path(state_path)
    if state_path.parent.exists() and any(state_path.parent.iterdir()):
        raise FileExistsError('Acceptance directory is not empty; preserve the previous attempt')
    config = json.loads(Path(config_path).read_text(encoding='utf-8'))
    name = checked_database_name('ais_lse_acceptance_' + datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_') + secrets.token_hex(3))
    state = {'database': name, 'media': str(state_path.parent / 'media'), 'password': secrets.token_urlsafe(24),
        'django_secret': secrets.token_urlsafe(48), 'status': 'preparing'}
    env = runtime_env(config, state)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    with state_path.open('x', encoding='utf-8') as saved:
        json.dump(state, saved, ensure_ascii=False)
    Path(state['media']).mkdir()
    import psycopg
    from psycopg import sql
    with psycopg.connect(host=env['PGHOST'], port=env['PGPORT'], user=env['PGUSER'], password=env['PGPASSWORD'],
                         dbname='postgres', autocommit=True, connect_timeout=3) as conn:
        if conn.execute('SELECT 1 FROM pg_database WHERE datname=%s', (name,)).fetchone():
            raise FileExistsError('Generated acceptance database exists; no overwrite')
        conn.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0 ENCODING 'UTF8'").format(sql.Identifier(name)))
    flags = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
    subprocess.run([sys.executable, 'manage.py', 'migrate', '--noinput'], cwd=ROOT / 'backend', env=env, check=True, **flags)
    setup_django(config, state)
    sys.path.insert(0, str(ROOT / 'backend/tests'))
    from full_workflow_support import create_people
    state['people'] = create_people(state['password'])
    state['status'] = 'ready'
    state_path.write_text(json.dumps(state, ensure_ascii=False), encoding='utf-8')
    print(f'Prepared isolated database {name}. Credentials: {state_path}; no working data changed.')
    return state


def serve(state_path=STATE):
    from socketserver import ThreadingMixIn
    from wsgiref.simple_server import WSGIServer, make_server
    from infra.acceptance_static import spa_application
    state_path = checked_state_path(state_path)
    state = json.loads(state_path.read_text(encoding='utf-8'))
    checked_database_name(state['database'])
    expected_media = state_path.parent / 'media'
    if state.get('status') != 'ready' or Path(state['media']).resolve() != expected_media.resolve() or not expected_media.resolve().is_relative_to(state_path.parent):
        raise ValueError('Only a ready isolated state with its own media directory may be served')
    config = json.loads(CONFIG.read_text(encoding='utf-8'))
    setup_django(config, state)
    from django.core.wsgi import get_wsgi_application
    app = spa_application(get_wsgi_application(), ROOT / 'frontend/dist')
    build = {str(path.relative_to(ROOT / 'frontend/dist')): hashlib.sha256(path.read_bytes()).hexdigest()
             for path in (ROOT / 'frontend/dist').rglob('*') if path.is_file()}
    (state_path.parent / 'served-build.json').write_text(json.dumps(build), encoding='utf-8')
    class ThreadingServer(ThreadingMixIn, WSGIServer):
        daemon_threads = True
    with make_server('127.0.0.1', 8001, app, server_class=ThreadingServer) as server:
        print(f'Isolated acceptance: http://127.0.0.1:8001/ · {state["database"]}', flush=True)
        try: server.serve_forever()
        except KeyboardInterrupt: pass


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'serve'])
    parser.add_argument('--state', type=Path, default=STATE)
    args = parser.parse_args()
    if args.command == 'prepare': prepare(state_path=args.state)
    else: serve(args.state)
