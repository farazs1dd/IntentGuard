"""Small single-process MVP store; secrets are redacted before persistence."""
from __future__ import annotations

import json
import os
import re
import sqlite3
from pathlib import Path

_SECRET_VALUES = set()


def register_secret(value):
    """Host-only redaction memory; never exported to agents or written to disk."""
    if isinstance(value, str) and len(value) >= 8:
        _SECRET_VALUES.add(value)


def redact(value):
    replacements = [
        secret for name, secret in os.environ.items()
        if re.search(r"KEY|TOKEN|PASSWORD|SECRET", name) and len(secret) >= 8
    ]
    replacements.extend(_SECRET_VALUES)

    def walk(item):
        if isinstance(item, dict):
            return {
                k: "[REDACTED]" if isinstance(v, str) and not k.endswith("_env") and re.search(
                    r"password|secret|api[_-]?key|authorization|token", k, re.IGNORECASE
                ) else walk(v) for k, v in item.items()
            }
        if isinstance(item, list):
            return [walk(v) for v in item]
        if isinstance(item, str):
            for secret in replacements:
                item = item.replace(secret, "[REDACTED]")
            item = re.sub(r"\bsk-(?:ant-)?[A-Za-z0-9_-]{16,}", "[REDACTED]", item)
        return item

    return walk(value)


class Store:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS documents "
            "(kind TEXT, id TEXT, owner TEXT, payload TEXT NOT NULL, "
            "PRIMARY KEY(kind,id))"
        )
        self.db.commit()

    def put(self, kind, owner, data):
        safe = redact(data)
        with self.db:
            self.db.execute(
                "INSERT INTO documents VALUES(?,?,?,?) ON CONFLICT(kind,id) "
                "DO UPDATE SET payload=excluded.payload WHERE owner=excluded.owner",
                (kind, data["id"], owner, json.dumps(safe)),
            )
        return safe

    def batch(self, owner, documents):
        """Commit related policy/campaign records together."""
        with self.db:
            for kind, data in documents:
                safe = redact(data)
                self.db.execute(
                    "INSERT INTO documents VALUES(?,?,?,?) ON CONFLICT(kind,id) "
                    "DO UPDATE SET payload=excluded.payload WHERE owner=excluded.owner",
                    (kind, data["id"], owner, json.dumps(safe)),
                )

    def get(self, kind, owner, identifier):
        row = self.db.execute(
            "SELECT payload FROM documents WHERE kind=? AND id=? AND owner=?",
            (kind, identifier, owner),
        ).fetchone()
        if row is None:
            raise KeyError("Resource not found")
        return json.loads(row[0])

    def list(self, kind, owner):
        rows = self.db.execute(
            "SELECT payload FROM documents WHERE kind=? AND owner=? ORDER BY rowid DESC",
            (kind, owner),
        )
        return [json.loads(row[0]) for row in rows]

    def close(self):
        self.db.close()

    def update(self, kind, owner, identifier, change):
        """Complete read/modify/write before any await or competing reservation."""
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            data = self.get(kind, owner, identifier)
            change(data)
            safe = redact(data)
            self.db.execute(
                "UPDATE documents SET payload=? WHERE kind=? AND id=? AND owner=?",
                (json.dumps(safe), kind, identifier, owner),
            )
        return safe
