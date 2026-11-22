"""Persistence for applications + append-only audit log.

Repository pattern: the workflow/API depend on the `Repo` interface; Postgres in the
app, in-memory in unit tests. (LangGraph's own checkpoints live in separate tables.)
"""

import datetime as dt
import json
from abc import ABC, abstractmethod
from typing import Any

from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from .pii import mask_value

SCHEMA = """
CREATE TABLE IF NOT EXISTS applications (
    id             TEXT PRIMARY KEY,
    status         TEXT NOT NULL,
    applicant_name TEXT,
    flag_count     INT NOT NULL DEFAULT 0,
    profile        JSONB,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS audit_log (
    id             BIGSERIAL PRIMARY KEY,
    application_id TEXT NOT NULL REFERENCES applications(id),
    ts             TIMESTAMPTZ NOT NULL DEFAULT now(),
    actor          TEXT NOT NULL,
    action         TEXT NOT NULL,
    detail         JSONB NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS audit_log_app ON audit_log(application_id, id);
"""
FIELDS = ("status", "applicant_name", "flag_count", "profile")


class Repo(ABC):
    @abstractmethod
    def create(self, app_id: str) -> None: ...

    @abstractmethod
    def update(self, app_id: str, **fields: Any) -> None: ...

    @abstractmethod
    def get(self, app_id: str) -> dict | None: ...

    @abstractmethod
    def recent(self, limit: int = 100, statuses: list[str] | None = None) -> list[dict]: ...

    @abstractmethod
    def _append_audit(self, app_id: str, actor: str, action: str, detail: dict) -> None: ...

    @abstractmethod
    def audit_trail(self, app_id: str) -> list[dict]: ...

    def audit(self, app_id: str, actor: str, action: str, detail: dict | None = None) -> None:
        """Every audit write goes through here, so PII is masked in one place."""
        self._append_audit(app_id, actor, action, mask_value("", detail or {}))


class InMemoryRepo(Repo):
    def __init__(self):
        self.apps: dict[str, dict] = {}
        self.events: list[dict] = []

    def create(self, app_id):
        now = dt.datetime.now(dt.UTC)
        self.apps[app_id] = {"id": app_id, "status": "processing", "applicant_name": None,
                             "flag_count": 0, "profile": None, "created_at": now, "updated_at": now}

    def update(self, app_id, **fields):
        assert set(fields) <= set(FIELDS), fields
        self.apps[app_id].update(fields, updated_at=dt.datetime.now(dt.UTC))

    def get(self, app_id):
        return self.apps.get(app_id)

    def recent(self, limit=100, statuses=None):
        rows = [a for a in self.apps.values() if not statuses or a["status"] in statuses]
        return sorted(rows, key=lambda a: a["created_at"], reverse=True)[:limit]

    def _append_audit(self, app_id, actor, action, detail):
        self.events.append({"id": len(self.events) + 1, "application_id": app_id, "ts": dt.datetime.now(dt.UTC),
                            "actor": actor, "action": action, "detail": json.loads(json.dumps(detail, default=str))})

    def audit_trail(self, app_id):
        return [e for e in self.events if e["application_id"] == app_id]


class PostgresRepo(Repo):
    def __init__(self, pool: ConnectionPool):
        self.pool = pool
        with pool.connection() as c:
            for stmt in filter(str.strip, SCHEMA.split(";")):  # one at a time: pool prepares statements
                c.execute(stmt)

    def _q(self, sql: str, params: tuple = (), fetch: str | None = None):
        with self.pool.connection() as c:
            cur = c.execute(sql, params)
            return cur.fetchone() if fetch == "one" else cur.fetchall() if fetch == "all" else None

    def create(self, app_id):
        self._q("INSERT INTO applications (id, status) VALUES (%s, 'processing')", (app_id,))

    def update(self, app_id, **fields):
        assert fields and set(fields) <= set(FIELDS), fields  # column names are whitelisted, values are params
        cols = ", ".join(f"{k} = %s" for k in fields)
        vals = tuple(Jsonb(v) if k == "profile" else v for k, v in fields.items())
        self._q(f"UPDATE applications SET {cols}, updated_at = now() WHERE id = %s", (*vals, app_id))

    def get(self, app_id):
        return self._q("SELECT * FROM applications WHERE id = %s", (app_id,), "one")

    def recent(self, limit=100, statuses=None):
        if statuses:
            return self._q("SELECT * FROM applications WHERE status = ANY(%s) ORDER BY created_at DESC LIMIT %s",
                           (statuses, limit), "all")
        return self._q("SELECT * FROM applications ORDER BY created_at DESC LIMIT %s", (limit,), "all")

    def _append_audit(self, app_id, actor, action, detail):
        self._q("INSERT INTO audit_log (application_id, actor, action, detail) VALUES (%s, %s, %s, %s)",
                (app_id, actor, action, Jsonb(json.loads(json.dumps(detail, default=str)))))

    def audit_trail(self, app_id):
        return self._q("SELECT * FROM audit_log WHERE application_id = %s ORDER BY id", (app_id,), "all")
