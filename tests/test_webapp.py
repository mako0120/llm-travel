import unittest
import io
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
import travel.webapp
from travel.webapp import application

class WebAppTests(unittest.TestCase):
    def request(self,path):
        seen=[]
        body=b''.join(application({'PATH_INFO':path},lambda status,headers:seen.extend([status,headers])))
        return seen,body
    def post(self,path,payload):
        raw=json.dumps(payload).encode();seen=[]
        return seen,b''.join(application({'PATH_INFO':path,'REQUEST_METHOD':'POST','CONTENT_LENGTH':str(len(raw)),'wsgi.input':io.BytesIO(raw)},lambda status,headers:seen.extend([status,headers])))
    def test_assets_are_served(self):
        seen,body=self.request('/')
        self.assertEqual(seen[0],'200 OK');self.assertIn('AI旅行計画',body.decode())
        self.assertIn('text/css',self.request('/style.css')[0][1][0][1])
    def test_planner_api_collects_questions(self):
        _,body=self.post('/api/planner',{'session_id':'test','message':'はい'})
        self.assertEqual(json.loads(body)['step'],1)
    def test_complete_conversation_creates_requested_research_run(self):
        session='ready-test';self.post('/api/planner',{'session_id':session,'message':'はい'})
        for answer in ['大阪','京都','1','グルメ','両方','50000','ホテル','公共交通','なし']:
            _,body=self.post('/api/planner',{'session_id':session,'message':answer})
        self.assertEqual(json.loads(body)['research']['state'],'requested')

    def test_path_traversal_outside_web_root_is_rejected(self):
        for path in ['/../CLAUDE.md', '/../../CLAUDE.md', '/../AGENTS.md']:
            seen, _ = self.request(path)
            self.assertEqual(seen[0], '404 Not Found', path)

    def test_path_traversal_cannot_read_a_sibling_html_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            web_root = base / "web"
            web_root.mkdir()
            (web_root / "index.html").write_text("<html>ok</html>", encoding="utf-8")
            secret = base / "secret.html"
            secret.write_text("SECRET", encoding="utf-8")
            with patch.object(travel.webapp, "ROOT", web_root):
                seen, body = self.request("/../secret.html")
                self.assertEqual(seen[0], "404 Not Found")
                self.assertNotIn(b"SECRET", body)

    def test_malformed_request_body_returns_400_not_a_crash(self):
        seen = []
        body = b''.join(application({'PATH_INFO': '/api/planner', 'REQUEST_METHOD': 'POST',
                                     'CONTENT_LENGTH': 'not-a-number', 'wsgi.input': io.BytesIO(b'{}')},
                                    lambda status, headers: seen.extend([status, headers])))
        self.assertEqual(seen[0], '400 Bad Request')
        seen = []
        body = b''.join(application({'PATH_INFO': '/api/planner', 'REQUEST_METHOD': 'POST',
                                     'CONTENT_LENGTH': '7', 'wsgi.input': io.BytesIO(b'{broken')},
                                    lambda status, headers: seen.extend([status, headers])))
        self.assertEqual(seen[0], '400 Bad Request')
