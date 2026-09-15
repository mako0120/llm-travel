"""Local-only browser shell for the guided travel planner."""
from http import HTTPStatus
import json
import os
from pathlib import Path
from urllib.parse import parse_qs
from wsgiref.simple_server import make_server
from travel.storage import Repository
from travel.planner import PlannerSession, next_turn, research_request


ROOT = Path(__file__).resolve().parents[1] / "web"
SESSIONS = {}
RESEARCH_RUNS = {}


def _read_json_body(environ):
    """Return the parsed JSON body, or None if it is missing or malformed."""
    try:
        size = int(environ.get("CONTENT_LENGTH") or 0)
    except ValueError:
        return None
    try:
        return json.loads(environ["wsgi.input"].read(size))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def _bad_request(start_response, message):
    start_response("400 Bad Request", [("Content-Type", "application/json; charset=utf-8")])
    return [json.dumps({"error": message}, ensure_ascii=False).encode("utf-8")]


def _repository():
    db_path = os.environ.get("LLM_TRAVEL_DB", "data/travel.sqlite3")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    return Repository(db_path)


def _json_response(start_response, payload, status="200 OK"):
    start_response(status, [("Content-Type", "application/json; charset=utf-8")])
    return [json.dumps(payload, ensure_ascii=False).encode("utf-8")]


def _research_status(run):
    return {"run_id": run["id"], "state": run["state"],
            "fresh_verified_evidence_count": len(run.get("fresh_verified_evidence", [])),
            "message": {"requested": "情報収集の準備中です。未確認の旅行情報は表示しません。",
                        "researching": "情報を確認中です。未確認の旅行情報は表示しません。",
                        "ready": "検証済みの情報を受信しました。",
                        "unconfigured": "情報提供元が未設定です。未確認の旅行情報は表示しません。",
                        "failed": "情報収集に失敗しました。未確認の旅行情報は表示しません。"}[run["state"]]}


def application(environ, start_response):
    path = environ.get("PATH_INFO", "/")
    method = environ.get("REQUEST_METHOD", "GET")
    if path == "/api/planner" and method == "POST":
        data = _read_json_body(environ)
        if not isinstance(data, dict):
            return _bad_request(start_response, "request body must be a JSON object")
        session_id = data.get("session_id", "local")
        session, result = next_turn(SESSIONS.get(session_id, PlannerSession()), data.get("message"))
        SESSIONS[session_id] = session
        if result["state"] == "ready" and session_id not in RESEARCH_RUNS:
            request = research_request(session, f"local-{session_id}", f"planner-{session_id}")
            repo = _repository()
            try:
                run = repo.create_research_run(request["profile_id"], request["requirements"], request["source_targets"])
            finally:
                repo.close()
            RESEARCH_RUNS[session_id] = run["id"]
        if session_id in RESEARCH_RUNS:
            repo = _repository()
            try:
                run = repo.get_research_run(RESEARCH_RUNS[session_id])
                if run is not None:
                    run["fresh_verified_evidence"] = repo.fresh_verified_evidence(run["id"])
                    result["research"] = _research_status(run)
            finally:
                repo.close()
        return _json_response(start_response, {"session_id": session_id, **result})
    if path.startswith("/api/research/"):
        parts = path.split("/")
        if len(parts) not in (4, 5) or not parts[3]:
            return _bad_request(start_response, "research run id is required")
        run_id = parts[3]
        action = parts[4] if len(parts) == 5 else None
        repo = _repository()
        try:
            if method == "GET" and action is None:
                run = repo.get_research_run(run_id)
                if run is None:
                    return _json_response(start_response, {"error": "research run not found"}, "404 Not Found")
                run["fresh_verified_evidence"] = repo.fresh_verified_evidence(run_id)
                return _json_response(start_response, {"research": _research_status(run), "evidence": run["evidence"]})
            data = _read_json_body(environ)
            if not isinstance(data, dict):
                return _bad_request(start_response, "request body must be a JSON object")
            if method == "POST" and action == "evidence":
                evidence = repo.record_evidence(run_id, data)
                return _json_response(start_response, {"evidence": evidence, "state": "researching"})
            if method == "POST" and action == "complete":
                run = repo.complete_research_run(run_id, data.get("state"))
                run["fresh_verified_evidence"] = repo.fresh_verified_evidence(run_id)
                return _json_response(start_response, {"research": _research_status(run)})
            return _json_response(start_response, {"error": "research endpoint not found"}, "404 Not Found")
        except ValueError as exc:
            return _bad_request(start_response, str(exc))
        finally:
            repo.close()
    if path == "/api/dialogue":
        query = parse_qs(environ.get("QUERY_STRING", ""))
        repo = _repository()
        try:
            if method == "POST":
                data = _read_json_body(environ)
                if not isinstance(data, dict) or not isinstance(data.get("body"), dict):
                    return _bad_request(start_response, "request body must be a JSON object with a 'body' field")
                message = repo.post_agent_message(data.get("conversation_id", "ai-001"), "human", "question", data["body"])
                payload = {"message": message}
            else:
                try:
                    after = int(query.get("after", ["0"])[0])
                except ValueError:
                    return _bad_request(start_response, "after must be an integer")
                payload = {"messages": repo.read_agent_messages(query.get("conversation_id", ["ai-001"])[0], after)}
        finally:
            repo.close()
        return _json_response(start_response, payload)
    requested = "index.html" if path == "/" else path.lstrip("/")
    root = ROOT.resolve()
    target = (ROOT / requested).resolve()
    if (not target.is_relative_to(root) or not target.is_file()
            or target.suffix not in {".html", ".css", ".js"}):
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
