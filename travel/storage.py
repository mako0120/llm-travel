"""SQLite persistence for immutable plans and human-approved improvement rules."""

import json
import sqlite3
import threading
from datetime import datetime, timezone
from uuid import uuid4
import hashlib


def _now():
    return datetime.now(timezone.utc).isoformat()


def _json(value):
    try:
        return json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("Data must be JSON serializable") from exc


def _identifier(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("id must be a nonempty string")
    return value


def _timestamp(value):
    if not isinstance(value, str):
        raise ValueError("timestamp must be an ISO string with timezone")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
    except ValueError as exc:
        raise ValueError("timestamp must be an ISO string with timezone") from exc
    if parsed.utcoffset() is None:
        raise ValueError("timestamp must include timezone")
    return parsed


def _exact(left, right):
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(_exact(left[key], right[key]) for key in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(_exact(a, b) for a, b in zip(left, right))
    return left == right


class Repository:
    """A local repository; each plan revision is inserted, never overwritten."""

    def __init__(self, path):
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(str(path), check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self.initialize()

    def initialize(self):
        with self._lock, self._connection:
            self._connection.executescript("""
                CREATE TABLE IF NOT EXISTS plans (
                    id TEXT NOT NULL,
                    version INTEGER NOT NULL CHECK(version > 0),
                    document TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(id, version)
                );
                CREATE TABLE IF NOT EXISTS feedback (
                    id TEXT PRIMARY KEY,
                    plan_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    ratings TEXT NOT NULL,
                    comment TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(plan_id, version) REFERENCES plans(id, version)
                );
                CREATE TABLE IF NOT EXISTS rules (
                    id TEXT PRIMARY KEY,
                    condition TEXT NOT NULL,
                    problem TEXT NOT NULL,
                    improvement TEXT NOT NULL,
                    evidence TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('pending', 'approved')),
                    created_at TEXT NOT NULL,
                    approved_at TEXT
                );
                CREATE TABLE IF NOT EXISTS research_runs (
                    id TEXT PRIMARY KEY,
                    profile_id TEXT NOT NULL,
                    requirements TEXT NOT NULL,
                    source_targets TEXT NOT NULL,
                    state TEXT NOT NULL CHECK(state IN ('requested', 'researching', 'ready', 'failed', 'unconfigured')),
                    created_at TEXT NOT NULL,
                    completed_at TEXT
                );
                CREATE TABLE IF NOT EXISTS research_evidence (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    agent TEXT NOT NULL CHECK(agent IN ('claude', 'codex', 'human', 'provider')),
                    source_type TEXT NOT NULL,
                    url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    facts TEXT NOT NULL,
                    retrieved_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    verification_status TEXT NOT NULL CHECK(verification_status IN ('verified', 'unverified')),
                    content_hash TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES research_runs(id)
                );
                CREATE TABLE IF NOT EXISTS preference_signals (
                    id TEXT PRIMARY KEY,
                    profile_id TEXT NOT NULL,
                    preference_key TEXT NOT NULL,
                    preference_value TEXT NOT NULL,
                    weight REAL NOT NULL,
                    source_feedback_id TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(source_feedback_id) REFERENCES feedback(id)
                );
                CREATE TABLE IF NOT EXISTS agent_messages (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    id TEXT NOT NULL UNIQUE,
                    conversation_id TEXT NOT NULL,
                    author TEXT NOT NULL CHECK(author IN ('claude', 'codex', 'human')),
                    message_type TEXT NOT NULL CHECK(message_type IN ('position', 'question', 'response', 'decision', 'handoff')),
                    body TEXT NOT NULL,
                    reply_to TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(reply_to) REFERENCES agent_messages(id)
                );
            """)

    def close(self):
        with self._lock:
            self._connection.close()

    def create_plan(self, plan):
        if not isinstance(plan, dict):
            raise ValueError("plan must be an object")
        plan_id = _identifier(plan["id"]) if "id" in plan else str(uuid4())
        with self._lock, self._connection:
            self._connection.execute("BEGIN IMMEDIATE")
            previous = self._connection.execute(
                "SELECT MAX(version) FROM plans WHERE id = ?", (plan_id,)
            ).fetchone()[0]
            document = dict(plan, id=plan_id, version=(previous or 0) + 1)
            encoded = _json(document)
            self._connection.execute(
                "INSERT INTO plans(id, version, document, created_at) VALUES (?, ?, ?, ?)",
                (plan_id, document["version"], encoded, _now()),
            )
            return json.loads(encoded)

    def get_plan(self, plan_id, version=None):
        _identifier(plan_id)
        if version is not None and (type(version) is not int or version < 1):
            raise ValueError("version must be a positive integer")
        with self._lock:
            if version is None:
                row = self._connection.execute(
                    "SELECT document FROM plans WHERE id = ? ORDER BY version DESC LIMIT 1",
                    (plan_id,),
                ).fetchone()
            else:
                row = self._connection.execute(
                    "SELECT document FROM plans WHERE id = ? AND version = ?",
                    (plan_id, version),
                ).fetchone()
            return json.loads(row["document"]) if row else None

    def add_feedback(self, plan_id, version, ratings, comment):
        _identifier(plan_id)
        if not isinstance(ratings, dict) or not ratings:
            raise ValueError("ratings must be a nonempty object")
        if any(not isinstance(k, str) or not k.strip() or type(v) is not int or not 1 <= v <= 5
               for k, v in ratings.items()):
            raise ValueError("ratings must have named integer scores from 1 to 5")
        if not isinstance(comment, str):
            raise ValueError("comment must be a string")
        if type(version) is not int or version < 1:
            raise ValueError("version must be a positive integer")
        record = dict(id=str(uuid4()), plan_id=plan_id, version=version,
                      ratings=json.loads(_json(ratings)), comment=comment, created_at=_now())
        with self._lock, self._connection:
            if self.get_plan(plan_id, version) is None:
                raise ValueError("Referenced plan version does not exist")
            self._connection.execute(
                "INSERT INTO feedback VALUES (?, ?, ?, ?, ?, ?)",
                (record["id"], plan_id, version, _json(ratings), comment, record["created_at"]),
            )
        return record

    def list_feedback(self, plan_id):
        _identifier(plan_id)
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM feedback WHERE plan_id = ? ORDER BY created_at, id", (plan_id,)
            ).fetchall()
            return [dict(dict(row), ratings=json.loads(row["ratings"])) for row in rows]

    def propose_rule(self, condition, problem, improvement, evidence):
        if not isinstance(condition, dict) or not condition:
            raise ValueError("condition must be a nonempty object")
        if any(not isinstance(key, str) or not key.strip() for key in condition):
            raise ValueError("condition keys must be nonempty strings")
        if any(not isinstance(value, str) or not value.strip() for value in (problem, improvement)):
            raise ValueError("problem and improvement must be nonempty strings")
        if not evidence:
            raise ValueError("evidence is required")
        record = dict(id=str(uuid4()), condition=json.loads(_json(condition)),
                      problem=problem, improvement=improvement,
                      evidence=json.loads(_json(evidence)), status="pending",
                      created_at=_now(), approved_at=None)
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT INTO rules VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (record["id"], _json(condition), problem, improvement, _json(evidence),
                 "pending", record["created_at"], None),
            )
        return record

    @staticmethod
    def _rule(row):
        return dict(dict(row), condition=json.loads(row["condition"]),
                    evidence=json.loads(row["evidence"]))

    def approve_rule(self, rule_id):
        _identifier(rule_id)
        with self._lock, self._connection:
            row = self._connection.execute("SELECT * FROM rules WHERE id = ?", (rule_id,)).fetchone()
            if row is None:
                raise ValueError("Rule does not exist")
            if row["status"] != "approved":
                self._connection.execute(
                    "UPDATE rules SET status = 'approved', approved_at = ? WHERE id = ?", (_now(), rule_id)
                )
                row = self._connection.execute("SELECT * FROM rules WHERE id = ?", (rule_id,)).fetchone()
            return self._rule(row)

    def find_rules(self, metadata):
        if not isinstance(metadata, dict):
            raise ValueError("metadata must be an object")
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM rules WHERE status = 'approved' ORDER BY created_at, id"
            ).fetchall()
            rules = [self._rule(row) for row in rows]
        return [rule for rule in rules if all(
            key in metadata and _exact(metadata[key], value)
            for key, value in rule["condition"].items()
        )]

    def create_research_run(self, profile_id, requirements, source_targets):
        """Create a request for an independent research agent; no agent is invoked here."""
        _identifier(profile_id)
        if not isinstance(requirements, dict) or not isinstance(source_targets, list):
            raise ValueError("requirements must be an object and source_targets must be a list")
        record = {"id": str(uuid4()), "profile_id": profile_id, "requirements": json.loads(_json(requirements)),
                  "source_targets": json.loads(_json(source_targets)), "state": "requested", "created_at": _now(), "completed_at": None}
        with self._lock, self._connection:
            self._connection.execute("INSERT INTO research_runs VALUES (?, ?, ?, ?, ?, ?, ?)",
                                     (record["id"], profile_id, _json(requirements), _json(source_targets), "requested", record["created_at"], None))
        return record

    def record_evidence(self, run_id, evidence):
        """Persist supplied research evidence with provenance; do not assert its truth."""
        _identifier(run_id)
        if not isinstance(evidence, dict):
            raise ValueError("evidence must be an object")
        agent = evidence.get("agent")
        if agent not in ("claude", "codex", "human", "provider"):
            raise ValueError("agent must identify the independent evidence producer")
        for key in ("source_type", "url", "title"):
            if not isinstance(evidence.get(key), str) or not evidence[key].strip():
                raise ValueError(f"{key} must be a nonempty string")
        if not isinstance(evidence.get("facts"), dict):
            raise ValueError("facts must be an object")
        retrieved_at = _timestamp(evidence.get("retrieved_at"))
        expires_at = _timestamp(evidence.get("expires_at"))
        if expires_at <= retrieved_at:
            raise ValueError("expires_at must follow retrieved_at")
        status = evidence.get("verification_status")
        if status not in ("verified", "unverified"):
            raise ValueError("verification_status must be verified or unverified")
        canonical = _json({key: evidence[key] for key in ("source_type", "url", "title", "facts", "retrieved_at", "expires_at", "verification_status")})
        record = {"id": str(uuid4()), "run_id": run_id, "agent": agent, "source_type": evidence["source_type"],
                  "url": evidence["url"], "title": evidence["title"], "facts": json.loads(_json(evidence["facts"])),
                  "retrieved_at": retrieved_at.isoformat(), "expires_at": expires_at.isoformat(), "verification_status": status,
                  "content_hash": hashlib.sha256(canonical.encode("utf-8")).hexdigest()}
        with self._lock, self._connection:
            run = self._connection.execute("SELECT state FROM research_runs WHERE id = ?", (run_id,)).fetchone()
            if run is None:
                raise ValueError("research run does not exist")
            if run["state"] in ("ready", "failed", "unconfigured"):
                raise ValueError("research run is already complete")
            self._connection.execute("UPDATE research_runs SET state = 'researching' WHERE id = ?", (run_id,))
            self._connection.execute("INSERT INTO research_evidence VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                     (record["id"], run_id, record["agent"], record["source_type"], record["url"], record["title"],
                                      _json(record["facts"]), record["retrieved_at"], record["expires_at"], status, record["content_hash"]))
        return record

    def complete_research_run(self, run_id, state):
        _identifier(run_id)
        if state not in ("ready", "failed", "unconfigured"):
            raise ValueError("research completion state is invalid")
        with self._lock, self._connection:
            row = self._connection.execute("SELECT state FROM research_runs WHERE id = ?", (run_id,)).fetchone()
            if row is None:
                raise ValueError("research run does not exist")
            count = self._connection.execute("SELECT COUNT(*) FROM research_evidence WHERE run_id = ?", (run_id,)).fetchone()[0]
            if state == "ready" and count == 0:
                raise ValueError("ready research must contain evidence")
            self._connection.execute("UPDATE research_runs SET state = ?, completed_at = ? WHERE id = ?", (state, _now(), run_id))
            return self.get_research_run(run_id)

    def get_research_run(self, run_id):
        _identifier(run_id)
        with self._lock:
            row = self._connection.execute("SELECT * FROM research_runs WHERE id = ?", (run_id,)).fetchone()
            if row is None:
                return None
            evidence = self._connection.execute("SELECT * FROM research_evidence WHERE run_id = ? ORDER BY retrieved_at, id", (run_id,)).fetchall()
        result = dict(dict(row), requirements=json.loads(row["requirements"]), source_targets=json.loads(row["source_targets"]))
        result["evidence"] = [dict(dict(item), facts=json.loads(item["facts"])) for item in evidence]
        return result

    def fresh_verified_evidence(self, run_id, now=None):
        now = now or datetime.now(timezone.utc)
        if not isinstance(now, datetime) or now.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        run = self.get_research_run(run_id)
        if run is None or run["state"] != "ready":
            return []
        return [item for item in run["evidence"] if item["verification_status"] == "verified" and _timestamp(item["expires_at"]) > now]

    def add_preference_signal(self, profile_id, preference_key, preference_value, weight, source_feedback_id=None):
        _identifier(profile_id)
        if not all(isinstance(value, str) and value.strip() for value in (preference_key, preference_value)):
            raise ValueError("preference key and value must be nonempty strings")
        if not isinstance(weight, (int, float)) or isinstance(weight, bool) or not -1 <= weight <= 1:
            raise ValueError("weight must be a number from -1 to 1")
        if source_feedback_id is not None:
            _identifier(source_feedback_id)
            with self._lock:
                if self._connection.execute("SELECT 1 FROM feedback WHERE id = ?", (source_feedback_id,)).fetchone() is None:
                    raise ValueError("source feedback does not exist")
        record = {"id": str(uuid4()), "profile_id": profile_id, "preference_key": preference_key, "preference_value": preference_value,
                  "weight": weight, "source_feedback_id": source_feedback_id, "created_at": _now()}
        with self._lock, self._connection:
            self._connection.execute("INSERT INTO preference_signals VALUES (?, ?, ?, ?, ?, ?, ?)", tuple(record.values()))
        return record

    def profile_context(self, profile_id):
        _identifier(profile_id)
        with self._lock:
            rows = self._connection.execute("SELECT * FROM preference_signals WHERE profile_id = ? ORDER BY created_at, id", (profile_id,)).fetchall()
        return [dict(row) for row in rows]

    def post_agent_message(self, conversation_id, author, message_type, body, reply_to=None):
        """Store a data-only message from its actual author; it does not invoke agents."""
        _identifier(conversation_id)
        if author not in ("claude", "codex", "human"):
            raise ValueError("author must identify the actual participant")
        if message_type not in ("position", "question", "response", "decision", "handoff"):
            raise ValueError("message type is invalid")
        if not isinstance(body, dict):
            raise ValueError("message body must be structured data")
        if reply_to is not None:
            _identifier(reply_to)
        record = {"id": str(uuid4()), "conversation_id": conversation_id, "author": author,
                  "message_type": message_type, "body": json.loads(_json(body)), "reply_to": reply_to, "created_at": _now()}
        with self._lock, self._connection:
            if reply_to is not None and self._connection.execute("SELECT 1 FROM agent_messages WHERE id = ?", (reply_to,)).fetchone() is None:
                raise ValueError("reply target does not exist")
            self._connection.execute("INSERT INTO agent_messages(id, conversation_id, author, message_type, body, reply_to, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                     (record["id"], conversation_id, author, message_type, _json(body), reply_to, record["created_at"]))
        return record

    def read_agent_messages(self, conversation_id, after_sequence=0):
        _identifier(conversation_id)
        if type(after_sequence) is not int or after_sequence < 0:
            raise ValueError("after_sequence must be a nonnegative integer")
        with self._lock:
            rows = self._connection.execute("SELECT * FROM agent_messages WHERE conversation_id = ? AND sequence > ? ORDER BY sequence", (conversation_id, after_sequence)).fetchall()
        return [dict(dict(row), body=json.loads(row["body"])) for row in rows]
