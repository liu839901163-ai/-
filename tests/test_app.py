import importlib.util
import base64
import io
import json
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from http.server import ThreadingHTTPServer

spec = importlib.util.spec_from_file_location('studio', Path(__file__).resolve().parents[1] / 'app.py')
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)


class StudioTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        app.DATA = Path(cls.temp.name)
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.temp.cleanup()

    def post(self, path, data, headers=None):
        return urllib.request.urlopen(urllib.request.Request(self.base + path, json.dumps(data).encode(), {'Content-Type': 'application/json', **(headers or {})}))

    def test_save_reload_and_export(self):
        doc = {'name': '测试保温杯', 'title': 'Steel bottle', 'material': 'Steel', 'moq': '100 pieces', 'description': '500 ml', 'keywords': 'bottle'}
        with self.post('/api/drafts', doc) as response:
            self.assertEqual(response.status, 201)
            draft_id = json.load(response)['id']
        with urllib.request.urlopen(self.base + '/api/drafts') as response:
            row = next(d for d in json.load(response) if d['id'] == draft_id)
        self.assertEqual(row['name'], doc['name'])
        # A fresh database connection must see the committed document.
        with app.connect() as db:
            self.assertEqual(json.loads(db.execute('SELECT document FROM drafts WHERE id=?', (draft_id,)).fetchone()[0]), doc)
        with self.post('/api/export', doc) as response:
            self.assertEqual(response.headers['Content-Type'], 'application/zip')
            with zipfile.ZipFile(io.BytesIO(response.read())) as archive:
                self.assertEqual(json.loads(archive.read('product.json')), doc)
                self.assertIn('未发布', archive.read('README.txt').decode())

    def test_reject_invalid_product(self):
        for doc in ({'name': 'no title'}, {'name': 'a', 'title': ['invalid']}, []):
            with self.assertRaises(urllib.error.HTTPError) as error:
                self.post('/api/drafts', doc)
            self.assertEqual(error.exception.code, 400)

    def test_cross_origin_write_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.post('/api/drafts', {'name': 'a', 'title': 'b'}, {'Origin': 'https://example.com'})
        self.assertEqual(error.exception.code, 403)

    def test_login_protects_pages_and_drafts(self):
        with patch.dict('os.environ', {'STUDIO_ACCESS_PASSWORD': 'test-only-password'}):
            for path in ['/', '/api/drafts', '/app.js']:
                with self.assertRaises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(self.base + path)
                self.assertEqual(error.exception.code, 401)
                self.assertIn('Basic', error.exception.headers['WWW-Authenticate'])
            with self.assertRaises(urllib.error.HTTPError) as error:
                self.post('/api/export', {'name': 'a', 'title': 'b'})
            self.assertEqual(error.exception.code, 401)
            for token, expected in [('studio:wrong-password', 401), ('wrong-user:test-only-password', 401), ('studio:test-only-password', 200)]:
                request = urllib.request.Request(self.base + '/api/drafts', headers={'Authorization': 'Basic ' + base64.b64encode(token.encode()).decode()})
                try:
                    with urllib.request.urlopen(request) as response:
                        self.assertEqual(response.status, expected)
                except urllib.error.HTTPError as error:
                    self.assertEqual(error.code, expected)
            with urllib.request.urlopen(self.base + '/api/health') as response:
                self.assertEqual(json.load(response)['status'], 'ok')

    def test_pages_health_and_missing_publish(self):
        for path, marker in [('/', '主图工作台'), ('/app.js', 'createImageBitmap'), ('/style.css', 'grid'), ('/api/health', 'not_connected')]:
            with urllib.request.urlopen(self.base + path) as response:
                self.assertEqual(response.status, 200)
                self.assertIn(marker, response.read().decode())
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.post('/api/publish', {'name': 'a', 'title': 'b'})
        self.assertEqual(error.exception.code, 404)


if __name__ == '__main__':
    unittest.main()
