"""Create local stand secrets without printing them or changing existing settings."""
import argparse
from pathlib import Path
import secrets

parser = argparse.ArgumentParser()
parser.add_argument('--host', required=True)
parser.add_argument('--port', type=int, default=8088)
args = parser.parse_args()
if not args.host or not 1 <= args.port <= 65535 or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-' for c in args.host):
    parser.error('Use an IPv4 address or hostname and a valid port.')
target = Path(__file__).with_name('.env')
if target.exists():
    print('Stand environment exists; secrets and settings retained.')
else:
    text = '\n'.join((
        'AIS_STAND_MODE=1', f'AIS_HTTP_PORT={args.port}',
        f'DJANGO_ALLOWED_HOSTS={args.host},127.0.0.1,localhost,backend',
        f'CSRF_TRUSTED_ORIGINS=http://{args.host}:{args.port},http://127.0.0.1:{args.port}',
        f'DJANGO_SECRET_KEY={secrets.token_urlsafe(64)}', f'PGPASSWORD={secrets.token_urlsafe(36)}',
        'COOKIE_SECURE=0', '',
    ))
    target.write_text(text, encoding='utf-8')
    target.chmod(0o600)
    print('Stand environment created; secrets were not printed.')
