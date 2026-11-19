"""Integration: real Postgres (docker compose up -d). Skipped when the DB is unreachable."""

import uuid

import psycopg
import pytest
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.types import Command
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from apps.api.config import Settings
from apps.api.repo import PostgresRepo
from apps.api.workflow import build_graph
from tests.fakes import TruthExtractor, applicant_with

URL = Settings().database_url
FILES = ["paystub.pdf", "w2.pdf", "statement.pdf"]


def _db_up() -> bool:
    try:
        psycopg.connect(URL, connect_timeout=2).close()
        return True
    except psycopg.OperationalError:
        return False


pytestmark = pytest.mark.skipif(not _db_up(), reason="Postgres not running (docker compose up -d)")


def process(applicant: str):
    """Everything a fresh API process would build: new pool, saver, repo, graph."""
    pool = ConnectionPool(URL, open=True, kwargs={"autocommit": True, "prepare_threshold": 0,
                                                  "row_factory": dict_row})
    saver = PostgresSaver(pool)
    saver.setup()
    repo = PostgresRepo(pool)
    extractor = TruthExtractor(applicant)
    return pool, repo, extractor, build_graph(extractor, repo, saver)


def test_restart_mid_review_loses_nothing():
    app_id, applicant = f"T-{uuid.uuid4().hex[:8]}", applicant_with("fake_employer")
    cfg = {"configurable": {"thread_id": app_id}}

    pool1, repo1, _, g1 = process(applicant)
    repo1.create(app_id)
    g1.invoke({"application_id": app_id, "files": FILES}, cfg)
    assert g1.get_state(cfg).next == ("review",)
    pool1.close()  # "process dies" mid-review

    pool2, repo2, extractor2, g2 = process(applicant)  # "process restarts"
    try:
        st = g2.get_state(cfg)
        assert st.next == ("review",) and "fake_employer" in {f["code"] for f in st.values["flags"]}
        out = g2.invoke(Command(resume={"decision": "reject", "reviewer": "priya",
                                        "edits": {"w2": {"ssn": "123-45-6789"}}}), cfg)
        assert out["status"] == "rejected" and extractor2.calls == 0
        row = repo2.get(app_id)
        assert row["status"] == "rejected" and row["profile"]["identity"]["ssn_last4"] == "6789"
        trail = repo2.audit_trail(app_id)
        assert [e["action"] for e in trail] == ["extracted", "flags_raised", "field_edited", "rejected"]
        edit = trail[2]["detail"]
        assert edit["new"] == "***-**-6789" and "123-45" not in str(trail)  # PII masked at rest
    finally:
        pool2.close()
