"""SQLite persistence for immutable plans and human-approved improvement rules."""

import json
import sqlite3
import threading
from datetime import datetime, timezone
from uuid import uuid4


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
