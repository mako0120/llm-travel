"""Local-only browser shell for the guided travel planner."""
from http import HTTPStatus
import json
import os
from pathlib import Path
from urllib.parse import parse_qs
from wsgiref.simple_server import make_server
from travel.storage import Repository
from travel.planner import PlannerSession, next_turn


ROOT = Path(__file__).resolve().parents[1] / "web"
SESSIONS = {}


def application(environ, start_response):
    path = environ.get("PATH_INFO", "/")
    if path == "/api/planner" and environ.get("REQUEST_METHOD") == "POST":
        size = int(environ.get("CONTENT_LENGTH") or 0)
        data = json.loads(environ["wsgi.input"].read(size))
        session_id = data.get("session_id", "local")
        session, result = next_turn(SESSIONS.get(session_id, PlannerSession()), data.get("message"))
        SESSIONS[session_id] = session
        start_response("200 OK", [("Content-Type", "application/json; charset=utf-8")])
        return [json.dumps({"session_id": session_id, **result}, ensure_ascii=False).encode("utf-8")]
    if path == "/api/dialogue":
        query = parse_qs(environ.get("QUERY_STRING", ""))
        repo = Repository(os.environ.get("LLM_TRAVEL_DB", "data/travel.sqlite3"))
        try:
            if environ.get("REQUEST_METHOD") == "POST":
                size = int(environ.get("CONTENT_LENGTH") or 0)
                data = json.loads(environ["wsgi.input"].read(size))
                message = repo.post_agent_message(data.get("conversation_id", "ai-001"), "human", "question", data["body"])
                payload = {"message": message}
            else:
                payload = {"messages": repo.read_agent_messages(query.get("conversation_id", ["ai-001"])[0], int(query.get("after", ["0"])[0]))}
        finally:
            repo.close()
        start_response("200 OK", [("Content-Type", "application/json; charset=utf-8")])
        return [json.dumps(payload, ensure_ascii=False).encode("utf-8")]
    target = ROOT / ("index.html" if path == "/" else path.lstrip("/"))
    if not target.is_file() or target.suffix not in {".html", ".css", ".js"}:
        start_response("404 Not Found", [("Content-Type", "text/plain; charset=utf-8")])
        return [b"Not found"]
    kinds = {".html": "text/html", ".css": "text/css", ".js": "application/javascript"}
    start_response("200 OK", [("Content-Type", kinds[target.suffix] + "; charset=utf-8")])
    return [target.read_bytes()]


def main():
    port = int(os.environ.get("LLM_TRAVEL_PORT", "8765"))
    with make_server("127.0.0.1", port, application) as server:
        print(f"Travel planner: http://127.0.0.1:{port}")
        server.serve_forever()


if __name__ == "__main__":
    main()
