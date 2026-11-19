"""Graph + API with in-memory checkpointer/repo and a truth-backed fake extractor."""

import logging
import shutil

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from apps.api.main import Deps, create_app
from apps.api.pii import PiiFilter, mask_text, mask_value
from apps.api.repo import InMemoryRepo
from apps.api.workflow import build_graph
from tests.fakes import SAMPLE, TruthExtractor, applicant_with

FILES = ["paystub.pdf", "w2.pdf", "statement.pdf"]
REVIEW = {"decision": "approve", "reviewer": "priya"}


def start(applicant, saver=None, repo=None, **kw):
    repo, saver = repo or InMemoryRepo(), saver or InMemorySaver()
    g = build_graph(TruthExtractor(applicant, **kw), repo, saver)
    repo.create("A1")
    out = g.invoke({"application_id": "A1", "files": FILES}, {"configurable": {"thread_id": "A1"}})
    return g, repo, saver, out


CFG = {"configurable": {"thread_id": "A1"}}


def test_pauses_at_review_with_flags():
    g, repo, _, out = start(applicant_with("fake_employer"))
    assert "__interrupt__" in out
    assert g.get_state(CFG).next == ("review",)
    assert "fake_employer" in {f["code"] for f in out["__interrupt__"][0].value["flags"]}
    assert repo.get("A1")["status"] == "in_review"


def test_resume_finalizes_and_audits_edits():
    g, repo, _, _ = start(applicant_with(None))
    out = g.invoke(Command(resume={**REVIEW, "edits": {"paystub": {"gross": "4,200.00"}},
                                   "notes": "verified by phone"}), CFG)
    assert out["status"] == "approved" and repo.get("A1")["profile"]["reviewer"] == "priya"
    assert out["extractions"]["paystub"]["data"]["gross"] == 420000
    actions = [e["action"] for e in repo.audit_trail("A1")]
    assert actions == ["extracted", "flags_raised", "field_edited", "approved"]


def test_restart_mid_review_loses_nothing():
    """New graph object (= new process) sharing only the checkpointer resumes the same run."""
    _, repo, saver, _ = start(applicant_with("overdrafts"))
    extractor = TruthExtractor(applicant_with("overdrafts"))
    g2 = build_graph(extractor, repo, saver)
    assert g2.get_state(CFG).next == ("review",)
    out = g2.invoke(Command(resume={**REVIEW, "decision": "reject"}), CFG)
    assert out["status"] == "rejected" and extractor.calls == 0  # no re-extraction


def test_extraction_failure_goes_to_review_not_crash():
    _, _, _, out = start(applicant_with(None), fail={"w2"})
    codes = {f["code"] for f in out["flags"]}
    assert "extraction_failed" in codes and "fake_employer" not in codes  # w2 rules skipped


def test_pii_masking(caplog):
    assert mask_text("ssn 950-49-2539 acct 1234567890123") == "ssn ***-**-2539 acct ****0123"
    assert mask_value("", {"field": "ssn", "old": "950-49-2539"})["old"] == "***-**-2539"
    rec = logging.LogRecord("x", logging.INFO, "", 0, "user %s", ("950-49-2539",), None)
    PiiFilter().filter(rec)
    assert rec.getMessage() == "user ***-**-2539"


# ---- API ------------------------------------------------------------------------------
@pytest.fixture
def client(tmp_path):
    app_dir = applicant_with("altered_totals")
    repo = InMemoryRepo()
    deps = Deps(repo, build_graph(TruthExtractor(app_dir), repo, InMemorySaver()), tmp_path)
    with TestClient(create_app(deps)) as c:
        c.files = [("files", (n, (SAMPLE / app_dir / n).read_bytes(), "application/pdf")) for n in FILES]
        yield c


def test_api_flow(client):
    app_id = client.post("/applications", files=client.files).json()["id"]
    a = client.get(f"/applications/{app_id}").json()  # TestClient runs background tasks before returning
    assert a["status"] == "in_review" and a["awaiting_review"]
    assert "altered_totals" in {f["code"] for f in a["flags"]}
    assert client.post(f"/applications/{app_id}/review",
                       json={**REVIEW, "edits": {"w2": {"ssn": "bad"}}}).status_code == 422
    done = client.post(f"/applications/{app_id}/review",
                       json={**REVIEW, "flag_decisions": {"altered_totals": "dismiss"}}).json()
    assert done["status"] == "approved" and not done["awaiting_review"]
    assert client.post(f"/applications/{app_id}/review", json=REVIEW).status_code == 409
    trail = [e["action"] for e in client.get(f"/applications/{app_id}/audit").json()]
    assert trail == ["uploaded", "extracted", "flags_raised", "review_submitted", "approved"]
    assert client.get(f"/applications/{app_id}/files/w2.pdf").status_code == 200
    assert client.get(f"/applications/{app_id}/files/..%2F..%2Fsecret").status_code == 404


def test_api_rejects_non_pdf(client):
    r = client.post("/applications", files=[("files", ("x.pdf", b"hello", "application/pdf"))])
    assert r.status_code == 422


@pytest.fixture(autouse=True, scope="module")
def _cleanup():
    yield
    shutil.rmtree(SAMPLE.parent / "uploads", ignore_errors=True)
