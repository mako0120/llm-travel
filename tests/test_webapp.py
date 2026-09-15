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

    def test_research_evidence_api_persists_status_and_fresh_verified_evidence(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict("os.environ", {"LLM_TRAVEL_DB": str(Path(tmp) / "travel.sqlite3")}):
            repo = travel.webapp._repository()
            try:
                run = repo.create_research_run("profile-test", {"destination": "京都"}, [])
            finally:
                repo.close()
            evidence = {"agent": "codex", "source_type": "official", "url": "https://example.org/hours",
                        "title": "営業時間", "facts": {"opening_hours": "synthetic"},
                        "retrieved_at": "2030-01-01T00:00:00Z", "expires_at": "2030-01-02T00:00:00Z",
                        "verification_status": "verified"}
            seen, body = self.post(f"/api/research/{run['id']}/evidence", evidence)
            self.assertEqual(seen[0], "200 OK")
            received = json.loads(body)
            self.assertEqual(received["state"], "researching")
            seen, body = self.post(f"/api/research/{run['id']}/complete", {"state": "ready"})
            self.assertEqual(seen[0], "200 OK")
            self.assertEqual(json.loads(body)["research"]["state"], "ready")
            seen, body = self.request(f"/api/research/{run['id']}")
            self.assertEqual(seen[0], "200 OK")
            self.assertEqual(json.loads(body)["research"]["fresh_verified_evidence_count"], 1)

    def test_itinerary_requires_two_real_reviews_and_evidence_for_alternatives(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict("os.environ", {"LLM_TRAVEL_DB": str(Path(tmp) / "travel.sqlite3")}):
            repo = travel.webapp._repository()
            try:
                run = repo.create_research_run("profile-test", {"destination": "京都"}, [])
                evidence = repo.record_evidence(run["id"], {"agent": "codex", "source_type": "official", "url": "https://example.org/place",
                    "title": "Synthetic place", "facts": {}, "retrieved_at": "2030-01-01T00:00:00Z", "expires_at": "2030-01-02T00:00:00Z", "verification_status": "verified"})
                repo.complete_research_run(run["id"], "ready")
            finally:
                repo.close()
            option = {"spot": "Synthetic place", "reason": "Synthetic evidence", "evidence_id": evidence["id"]}
            proposal = {"primary": [option], "spot_alternatives": [dict(option, spot="Alternative")],
                        "rainy_day_alternatives": [dict(option, spot="Rain alternative")],
                        "reviews": {"claude": {"decision": "approved", "rationale": "Reviewed"},
                                    "codex": {"decision": "approved", "rationale": "Validated"}}}
            seen, body = self.post(f"/api/research/{run['id']}/itinerary", proposal)
            self.assertEqual(seen[0], "200 OK")
            self.assertEqual(json.loads(body)["itinerary"]["rainy_day_alternatives"][0]["spot"], "Rain alternative")
            seen, body = self.request(f"/api/research/{run['id']}/itinerary")
            self.assertEqual(seen[0], "200 OK")
            self.assertEqual(json.loads(body)["itinerary"]["spot_alternatives"][0]["spot"], "Alternative")
        seen = []
        body = b''.join(application({'PATH_INFO': '/api/planner', 'REQUEST_METHOD': 'POST',
                                     'CONTENT_LENGTH': '7', 'wsgi.input': io.BytesIO(b'{broken')},
                                    lambda status, headers: seen.extend([status, headers])))
        self.assertEqual(seen[0], '400 Bad Request')
