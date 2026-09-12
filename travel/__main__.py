import argparse
import json
from pathlib import Path
from travel.domain import validate_plan, summarize_ratings
from travel.storage import Repository


def main():
    parser = argparse.ArgumentParser(description="llm-travel local research CLI")
    parser.add_argument("--db", default="data/travel.sqlite3")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "save", "feedback", "propose-rule", "find-rules"):
        sub.add_parser(name).add_argument("file", type=Path)
    for name in ("show", "analytics", "approve-rule"):
        sub.add_parser(name).add_argument("id")
    args = parser.parse_args()
    repo = None
    try:
        payload = json.loads(args.file.read_text(encoding="utf-8")) if hasattr(args, "file") else None
        if args.command == "validate":
            issues = validate_plan(payload)
            print(json.dumps({"valid": not issues, "issues": issues}, ensure_ascii=False, indent=2))
            return 1 if issues else 0
        Path(args.db).parent.mkdir(parents=True, exist_ok=True)
        repo = Repository(args.db)
        if args.command == "save":
            issues = validate_plan(payload)
            if issues:
                print(json.dumps({"saved": False, "issues": issues}, ensure_ascii=False, indent=2))
                return 1
            result = repo.create_plan(payload)
        elif args.command == "show":
            result = repo.get_plan(args.id)
            if result is None:
                raise ValueError("plan not found")
        elif args.command == "feedback":
            result = repo.add_feedback(payload["plan_id"], payload["version"], payload["ratings"], payload.get("comment", ""))
        elif args.command == "analytics":
            records = repo.list_feedback(args.id)
            categories = sorted({key for record in records for key in record["ratings"]})
            result = {key: summarize_ratings([r["ratings"][key] for r in records if key in r["ratings"]]) for key in categories}
        elif args.command == "propose-rule":
            result = repo.propose_rule(payload["condition"], payload["problem"], payload["improvement"], payload["evidence"])
        elif args.command == "approve-rule":
            result = repo.approve_rule(args.id)
        else:
            result = repo.find_rules(payload)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 2
    finally:
        if repo is not None:
            repo.close()


if __name__ == "__main__":
    raise SystemExit(main())
