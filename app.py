"""Local, single-user product studio. Run with python app.py."""
import io
import base64
import hmac
import json
import os
import sqlite3
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get('STUDIO_DATA_DIR', ROOT / '.data'))
MAX_BODY = 18 * 1024 * 1024


def connect():
    DATA.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DATA / 'studio.db')
    db.execute('CREATE TABLE IF NOT EXISTS drafts (id INTEGER PRIMARY KEY, document TEXT NOT NULL, updated TEXT DEFAULT CURRENT_TIMESTAMP)')
    return db


def validate(doc):
    if not isinstance(doc, dict):
        raise ValueError('产品资料格式错误')
    result = {}
    for key in ('name', 'title', 'material', 'moq', 'description', 'keywords'):
        value = doc.get(key, '')
        if not isinstance(value, str) or len(value) > 12000:
            raise ValueError('字段内容过长或格式错误')
        result[key] = value.strip()
    if not result['name'] or not result['title']:
        raise ValueError('请填写内部产品名和英文标题')
    return result


class Handler(BaseHTTPRequestHandler):
    def parse_request(self):
        if not super().parse_request():
            return False
        password = os.environ.get('STUDIO_ACCESS_PASSWORD', '')
        if password and urlsplit(self.path).path != '/api/health':
            expected = ('studio:' + password).encode()
            try:
                scheme, encoded = self.headers.get('Authorization', '').split(' ', 1)
                supplied = base64.b64decode(encoded, validate=True) if scheme.lower() == 'basic' else b''
            except (ValueError, TypeError):
                supplied = b''
            if not hmac.compare_digest(supplied, expected):
                self.reply(401, {'error': '请登录产品工作室'}, **{'WWW-Authenticate': 'Basic realm="Product Studio", charset="UTF-8"'})
                return False
        return True

    def reply(self, status, body, mime='application/json; charset=utf-8', **headers):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Cache-Control', 'no-store')
        for key, value in headers.items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/api/health':
            return self.reply(200, {'status': 'ok', 'publishing': 'not_connected'})
        if path == '/api/drafts':
            with connect() as db:
                rows = db.execute('SELECT id, document, updated FROM drafts ORDER BY id DESC').fetchall()
            return self.reply(200, [{'id': r[0], **json.loads(r[1]), 'updated': r[2]} for r in rows])
        files = {'/': ('index.html', 'text/html; charset=utf-8'), '/app.js': ('app.js', 'text/javascript; charset=utf-8'), '/style.css': ('style.css', 'text/css; charset=utf-8')}
        if path in files:
            filename, mime = files[path]
            return self.reply(200, (ROOT / 'static' / filename).read_bytes(), mime)
        self.reply(404, {'error': '页面不存在'})

    def do_POST(self):
        # Reject cross-site browser writes. This application is for local use.
        origin = self.headers.get('Origin')
        if origin and urlsplit(origin).netloc != self.headers.get('Host'):
            return self.reply(403, {'error': '不允许跨站请求'})
        if self.headers.get_content_type() != 'application/json':
            return self.reply(415, {'error': '需要 JSON 请求'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= MAX_BODY:
                return self.reply(413, {'error': '请求过大或为空'})
            payload = json.loads(self.rfile.read(length))
            doc = validate(payload)
            path = urlsplit(self.path).path
            if path == '/api/drafts':
                with connect() as db:
                    cursor = db.execute('INSERT INTO drafts(document) VALUES (?)', (json.dumps(doc, ensure_ascii=False),))
                    draft_id = cursor.lastrowid
                return self.reply(201, {'id': draft_id, 'status': 'draft'})
            if path == '/api/export':
                output = io.BytesIO()
                with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
                    archive.writestr('product.json', json.dumps(doc, ensure_ascii=False, indent=2))
                    archive.writestr('listing.txt', '\n\n'.join(f'{k}: {v}' for k, v in doc.items()))
                    archive.writestr('README.txt', '本资料包未发布到阿里巴巴国际站。请核对事实、类目、价格、认证和图片后，在商家后台上传。主图请使用页面上的下载按钮单独保存。')
                return self.reply(200, output.getvalue(), 'application/zip', **{'Content-Disposition': 'attachment; filename="product-package.zip"'})
            return self.reply(404, {'error': '接口不存在'})
        except (ValueError, TypeError, UnicodeDecodeError) as exc:
            self.reply(400, {'error': str(exc)})


if __name__ == '__main__':
    with connect():
        pass
    host = os.environ.get('HOST', '127.0.0.1')
    if host not in ('127.0.0.1', 'localhost', '::1') and not os.environ.get('STUDIO_ACCESS_PASSWORD'):
        raise SystemExit('Public binding requires STUDIO_ACCESS_PASSWORD')
    port = int(os.environ.get('PORT', '8000'))
    print(f'Product studio listening on {host}:{port}', flush=True)
    ThreadingHTTPServer((host, port), Handler).serve_forever()
