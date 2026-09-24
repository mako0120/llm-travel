"""Local-only browser shell for the guided travel planner."""
from http import HTTPStatus
import json
import os
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from wsgiref.simple_server import make_server
from travel.storage import Repository, validate_evidence_payload
from travel.planner import PlannerSession, next_turn, research_request
from travel.providers import GoogleMapsAdapter, google_places_evidence, public_provider_catalog
from travel.free_sources import collect_public_evidence, public_source_catalog
from travel.agent_research import agent_web_research_request, validate_agent_web_evidence
from travel.draft_itinerary import create_research_draft


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


def _forbidden(start_response, message):
    start_response("403 Forbidden", [("Content-Type", "application/json; charset=utf-8")])
    return [json.dumps({"error": message}, ensure_ascii=False).encode("utf-8")]


def _same_origin_request(environ):
    """Reject cross-site browser writes; local non-browser development calls remain supported."""
    if environ.get("HTTP_SEC_FETCH_SITE", "").lower() == "cross-site":
        return False
    origin = environ.get("HTTP_ORIGIN")
    if not origin:
        return True
    parsed = urlsplit(origin)
    if parsed.scheme != "http" or parsed.path or parsed.query or parsed.fragment:
        return False
    allowed_ports = {str(os.environ.get("LLM_TRAVEL_PORT", "8765")), "8765"}
    return parsed.hostname in {"127.0.0.1", "localhost"} and str(parsed.port or 80) in allowed_ports


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
    if method in {"POST", "PUT", "PATCH", "DELETE"} and path.startswith("/api/") and not _same_origin_request(environ):
        return _forbidden(start_response, "cross-origin browser requests are not allowed")
    if path == "/api/public/itineraries" and method == "GET":
        repo = _repository()
        try:
            return _json_response(start_response, {"itineraries": repo.list_published_itineraries()})
        finally:
            repo.close()
    if path.startswith("/api/public/itineraries/") and method == "GET":
        slug = path.removeprefix("/api/public/itineraries/")
        if not slug or "/" in slug:
            return _bad_request(start_response, "public itinerary slug is required")
        repo = _repository()
        try:
            result = repo.public_itinerary(slug)
            if result is None:
                return _json_response(start_response, {"error": "public itinerary not found"}, "404 Not Found")
            return _json_response(start_response, result)
        finally:
            repo.close()
    if path.startswith("/api/public/itineraries/") and path.endswith("/feedback") and method == "POST":
        slug = path.removeprefix("/api/public/itineraries/").removesuffix("/feedback").strip("/")
        data = _read_json_body(environ)
        if not slug or not isinstance(data, dict):
            return _bad_request(start_response, "public itinerary slug and JSON body are required")
        repo = _repository()
        try:
            feedback = repo.add_public_feedback(slug, data.get("rating"), data.get("comment", ""))
            return _json_response(start_response, {"feedback": feedback,
                "message": "評価を受け付けました。公開前に確認されます。"}, "202 Accepted")
        except ValueError as exc:
            return _bad_request(start_response, str(exc))
        finally:
            repo.close()
    if path.startswith("/api/itineraries/") and path.endswith("/publish") and method == "POST":
        itinerary_id = path.removeprefix("/api/itineraries/").removesuffix("/publish").strip("/")
        data = _read_json_body(environ)
        if not itinerary_id or not isinstance(data, dict):
            return _bad_request(start_response, "itinerary id and JSON body are required")
        repo = _repository()
        try:
            published = repo.publish_itinerary(itinerary_id, data.get("title"), data.get("slug"))
            return _json_response(start_response, {"published": published,
                                                   "public_url": f"/public.html?plan={published['slug']}"})
        except ValueError as exc:
            return _bad_request(start_response, str(exc))
        finally:
            repo.close()
    if path == "/api/providers" and method == "GET":
        return _json_response(start_response, {"providers": public_provider_catalog()})
    if path == "/api/free-sources" and method == "GET":
        return _json_response(start_response, {"sources": [item.__dict__ for item in public_source_catalog()]})
    if path == "/api/free-research" and method == "POST":
        data = _read_json_body(environ)
        if not isinstance(data, dict) or not isinstance(data.get("destination"), str):
            return _bad_request(start_response, "destination must be a string")
        destination = data["destination"].strip()
        if not destination or len(destination) > 160:
            return _bad_request(start_response, "destination must be 1 to 160 characters")
        if os.environ.get("LLM_TRAVEL_DEPLOYMENT_MODE", "research").lower() == "commercial":
            return _json_response(start_response, {
                "state": "commercial_provider_configuration_required",
                "message": "商用モードでは公開共有 API を呼び出しません。各情報源の商用契約・自己ホスト・ライセンス確認済み接続を設定してください。",
                "sources": [item.__dict__ for item in public_source_catalog()],
            }, "409 Conflict")
        # These are bounded, user-triggered requests.  Results stay unverified
        # until an operator reviews them against an authoritative source.
        results, evidence = collect_public_evidence(destination)
        return _json_response(start_response, {
            "destination": destination,
            "search_mode": "live_public_web",
            "results": [{"provider": result.provider, "state": result.state,
                         "value": result.value, "version": result.version} for result in results],
            "evidence": evidence,
            "notice": "インターネット上の無料公開情報を検索した候補です。時刻・料金・評価・営業状況は未検証のため旅程には使いません。",
        })
    if path == "/api/connected-research" and method == "POST":
        data = _read_json_body(environ)
        if not isinstance(data, dict) or not isinstance(data.get("destination"), str):
            return _bad_request(start_response, "destination must be a string")
        destination = data["destination"].strip()
        if not destination or len(destination) > 160:
            return _bad_request(start_response, "destination must be 1 to 160 characters")
        # The optional key is read only from the process environment. It is
        # never accepted from a browser request, stored, returned, or logged.
        result = GoogleMapsAdapter(os.environ.get("GOOGLE_MAPS_API_KEY")).search_places(
            f"{destination} 観光 レストラン", max_result_count=10)
        return _json_response(start_response, {
            "destination": destination,
            "provider": "google_maps",
            "state": result.state,
            "evidence": google_places_evidence(result),
            "notice": "Google Maps の候補は取得後も unverified です。評価・営業時間・料金・経路は公式根拠で確認するまで確定しません。",
        })
    if path == "/api/workspace/runs" and method == "POST":
        data = _read_json_body(environ)
        if not isinstance(data, dict) or not isinstance(data.get("requirements"), dict):
            return _bad_request(start_response, "requirements must be an object")
        requirements = data["requirements"]
        destination = requirements.get("destination")
        if not isinstance(destination, str) or not destination.strip() or len(destination) > 160:
            return _bad_request(start_response, "requirements.destination must be 1 to 160 characters")
        repo = _repository()
        try:
            run = repo.create_research_run("local-workspace", requirements, data.get("source_targets", []))
            return _json_response(start_response, {"run": run}, "201 Created")
        except ValueError as exc:
            return _bad_request(start_response, str(exc))
        finally:
            repo.close()
    if path == "/api/workspace/draft-preview" and method == "POST":
        data = _read_json_body(environ)
        requirements = data.get("requirements") if isinstance(data, dict) else None
        evidence = data.get("evidence") if isinstance(data, dict) else None
        if not isinstance(requirements, dict) or not isinstance(evidence, list) or not evidence:
            return _bad_request(start_response, "requirements and one or more evidence candidates are required")
        if len(evidence) > 20:
            return _bad_request(start_response, "at most 20 evidence candidates are allowed")
        try:
            # A preview is not persisted, so it has no database evidence ids.
            # Add transient references only for rendering; no travel fact is
            # created and the values never enter SQLite.
            safe_candidates = [dict(validate_evidence_payload(item), id=f"preview-{index}")
                               for index, item in enumerate(evidence, start=1)]
            return _json_response(start_response, {"draft": create_research_draft(requirements, safe_candidates),
                                                   "persistence": "preview_only"})
        except ValueError as exc:
            return _bad_request(start_response, str(exc))
    if path.startswith("/api/workspace/runs/") and path.endswith("/auto-worker-status") and method == "GET":
        run_id = path.removeprefix("/api/workspace/runs/").removesuffix("/auto-worker-status").strip("/")
        if not run_id:
            return _bad_request(start_response, "research run id is required")
        repo = _repository()
        try:
            run = repo.get_research_run(run_id)
            if run is None:
                return _json_response(start_response, {"error": "research run not found"}, "404 Not Found")
            return _json_response(start_response, {
                "run_id": run_id,
                "run_state": run["state"],
                "auto_worker": repo.latest_auto_worker_result(run_id),
                "notice": "This endpoint only reads a previously recorded worker result. It never starts the worker.",
            })
        except ValueError as exc:
            return _bad_request(start_response, str(exc))
        finally:
            repo.close()
    if path.startswith("/api/workspace/runs/") and path.endswith("/packet") and method == "POST":
        run_id = path.removeprefix("/api/workspace/runs/").removesuffix("/packet").strip("/")
        data = _read_json_body(environ)
        candidates = data.get("evidence") if isinstance(data, dict) else None
        if not run_id or not isinstance(candidates, list) or not candidates:
            return _bad_request(start_response, "run id and one or more evidence candidates are required")
        repo = _repository()
        try:
            saved = [repo.record_evidence(run_id, item) for item in candidates]
            return _json_response(start_response, {"run_id": run_id, "evidence": saved, "state": "researching"}, "201 Created")
        except ValueError as exc:
            return _bad_request(start_response, str(exc))
        finally:
            repo.close()
    if path.startswith("/api/workspace/runs/") and path.endswith("/draft") and method == "POST":
        run_id = path.removeprefix("/api/workspace/runs/").removesuffix("/draft").strip("/")
        if not run_id:
            return _bad_request(start_response, "research run id is required")
        repo = _repository()
        try:
            run = repo.get_research_run(run_id)
            if run is None:
                return _json_response(start_response, {"error": "research run not found"}, "404 Not Found")
            return _json_response(start_response, {"draft": create_research_draft(run["requirements"], run["evidence"])})
        except ValueError as exc:
            return _bad_request(start_response, str(exc))
        finally:
            repo.close()
    if path.startswith("/api/workspace/runs/") and path.endswith("/agent-research") and method == "POST":
        run_id = path.removeprefix("/api/workspace/runs/").removesuffix("/agent-research").strip("/")
        data = _read_json_body(environ)
        if not run_id or not isinstance(data, dict):
            return _bad_request(start_response, "run id and JSON body are required")
        repo = _repository()
        try:
            if data.get("action") == "request":
                run = repo.get_research_run(run_id)
                if run is None:
                    return _json_response(start_response, {"error": "research run not found"}, "404 Not Found")
                return _json_response(start_response, {"request": agent_web_research_request(run["requirements"]), "state": run["state"]})
            candidates = data.get("evidence")
            if not isinstance(candidates, list) or not candidates:
                return _bad_request(start_response, "agent research evidence is required")
            saved = [repo.record_evidence(run_id, validate_agent_web_evidence(item)) for item in candidates]
            return _json_response(start_response, {"run_id": run_id, "evidence": saved, "state": "researching"}, "201 Created")
        except ValueError as exc:
            return _bad_request(start_response, str(exc))
        finally:
            repo.close()
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
                return _json_response(start_response, {"research": _research_status(run), "evidence": run["evidence"],
                                                       "itinerary": repo.latest_itinerary_proposal(run_id)})
            if method == "GET" and action == "itinerary":
                itinerary = repo.latest_itinerary_proposal(run_id)
                if itinerary is None:
                    return _json_response(start_response, {"error": "itinerary is not ready"}, "404 Not Found")
                return _json_response(start_response, {"itinerary": itinerary})
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
            if method == "POST" and action == "itinerary":
                proposal = data.get("proposal", data)
                itinerary = repo.record_itinerary_proposal(run_id, proposal, data.get("before_itinerary_id"),
                                                            data.get("improvement_summary"))
                return _json_response(start_response, {"itinerary": itinerary})
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
