"""Serve the real compiled SPA beside Django in an isolated acceptance run only."""
import mimetypes
from pathlib import Path
from urllib.parse import unquote
from wsgiref.util import FileWrapper


def spa_application(api, root: Path):
    root = root.resolve()
    index = root / 'index.html'
    if not index.is_file():
        raise FileNotFoundError('Build frontend/dist before acceptance serving')

    def application(env, start):
        path = env.get('PATH_INFO', '/')
        if path == '/api' or path.startswith('/api/'):
            return api(env, start)
        decoded = unquote(path)
        invalid = '\x00' in decoded or '\\' in decoded or '..' in decoded.split('/')
        asset = decoded == '/assets' or decoded.startswith('/assets/')
        target = (root / decoded.lstrip('/')).resolve() if asset and not invalid else index
        if invalid or not target.is_relative_to(root) or not target.is_file():
            body = b'Not found'
            start('404 Not Found', [('Content-Type', 'text/plain'), ('Content-Length', str(len(body)))])
            return [] if env.get('REQUEST_METHOD') == 'HEAD' else [body]
        kind = mimetypes.guess_type(str(target))[0] or 'application/octet-stream'
        start('200 OK', [('Content-Type', kind), ('Content-Length', str(target.stat().st_size)), ('Cache-Control', 'no-store')])
        return [] if env.get('REQUEST_METHOD') == 'HEAD' else FileWrapper(target.open('rb'))
    return application
