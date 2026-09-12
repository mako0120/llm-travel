import unittest
import io
import json
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
