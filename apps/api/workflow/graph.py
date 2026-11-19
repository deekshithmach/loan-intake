"""LangGraph workflow:

    extract → validate → cross_check → review (interrupt) → finalize

State is plain JSON (dicts), so the Postgres checkpointer can persist it and a
restarted process resumes exactly where it paused.

Gotcha: on resume LangGraph re-runs the interrupted node from the top, so `review`
has no side effects before `interrupt()`. Writes happen in other nodes / the API.
"""

import logging
from pathlib import Path
from typing import Any, Literal, Protocol, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from pydantic import BaseModel, Field

from apps.api.extraction import ExtractionResult
from apps.api.repo import Repo
from apps.api.rules import Docs, Evidence, Flag, Severity, run_rules
from apps.api.schemas import SCHEMAS, DocType

log = logging.getLogger(__name__)
DOC_TYPES = [DocType.PAYSTUB, DocType.W2, DocType.STATEMENT]


class ExtractorLike(Protocol):
    def run(self, path: str | Path) -> ExtractionResult: ...


class State(TypedDict, total=False):
    application_id: str
    files: list[str]
    extractions: dict[str, dict]  # doc_type -> ExtractionResult.to_dict()
    flags: list[dict]
    review: dict
    status: str
    profile: dict


class Review(BaseModel):
    """What the underwriter sends to resume the graph."""

    decision: Literal["approve", "reject"]
    reviewer: str = Field(min_length=1)
    edits: dict[str, dict[str, Any]] = Field(default_factory=dict)  # {doc: {field: new_value}}
    flag_decisions: dict[str, Literal["accept", "dismiss"]] = Field(default_factory=dict)  # {code: ...}
    notes: str = ""


def ok_data(extractions: dict[str, dict]) -> dict[str, dict]:
    return {k: e["data"] for k, e in extractions.items() if e.get("ok")}


def apply_edits(extractions: dict[str, dict], edits: dict[str, dict]) -> tuple[dict[str, dict], list[dict]]:
    """Return (new extractions, change list). Raises ValueError if an edit breaks the schema."""
    out = {k: {**v, "data": dict(v["data"]) if v.get("data") else None} for k, v in extractions.items()}
    changes = []
    for doc, fields in edits.items():
        if doc not in out or not out[doc].get("data"):
            raise ValueError(f"no extracted data for '{doc}' to edit")
        data = out[doc]["data"]
        for field, new in fields.items():
            if field not in data:
                raise ValueError(f"unknown field {doc}.{field}")
            changes.append({"doc": doc, "field": field, "old": data[field], "new": new})
            data[field] = new
        try:  # re-validate so money strings → cents, dates parsed, etc.
            out[doc]["data"] = SCHEMAS[DocType(doc)].model_validate(data).model_dump(mode="json")
        except Exception as e:
            raise ValueError(f"edit makes {doc} invalid: {e}") from e
    return out, changes


def build_graph(extractor: ExtractorLike, repo: Repo, checkpointer):
    def extract(state: State) -> State:
        app_id, extractions, flags = state["application_id"], {}, []
        for f in state["files"]:
            r = extractor.run(f)
            key = r.doc_type.value
            if key in extractions:
                flags.append(Flag(code="duplicate_document", severity=Severity.LOW,
                                  message=f"More than one {key}; using {Path(f).name}",
                                  evidence=[Evidence(doc=key, field="file", value=Path(f).name)]))
            extractions[key] = r.to_dict()
            if not r.ok:
                flags.append(Flag(code="extraction_failed", severity=Severity.HIGH,
                                  message=f"Could not extract {Path(f).name}: {r.error}",
                                  evidence=[Evidence(doc=key, field="file", value=Path(f).name)]))
        for t in DOC_TYPES:
            if t.value not in extractions:
                flags.append(Flag(code="missing_document", severity=Severity.MEDIUM,
                                  message=f"No {t.value} provided", evidence=[]))
        usage = [e["usage"] for e in extractions.values()]
        repo.audit(app_id, "system", "extracted", {
            "docs": {k: {"ok": e["ok"], "scanned": e["scanned"], "attempts": e["attempts"]}
                     for k, e in extractions.items()},
            "llm_calls": sum(u["calls"] for u in usage), "cost_usd": round(sum(u["cost_usd"] for u in usage), 5)})
        return {"extractions": extractions, "flags": [f.model_dump() for f in flags]}

    def validate(state: State) -> State:
        flags = run_rules(Docs.from_data(ok_data(state["extractions"])), "validate")
        return {"flags": state["flags"] + [f.model_dump() for f in flags]}

    def cross_check(state: State) -> State:
        flags = run_rules(Docs.from_data(ok_data(state["extractions"])), "cross_check")
        all_flags = state["flags"] + [f.model_dump() for f in flags]
        app_id = state["application_id"]
        data = ok_data(state["extractions"])
        name = next((d[k] for d, k in ((data.get("w2"), "employee"), (data.get("paystub"), "employee"),
                                       (data.get("statement"), "account_holder")) if d), None)
        repo.update(app_id, status="in_review", applicant_name=name, flag_count=len(all_flags))
        repo.audit(app_id, "system", "flags_raised", {"codes": [f["code"] for f in all_flags]})
        return {"flags": all_flags, "status": "in_review"}

    def review(state: State) -> State:
        answer = interrupt({"application_id": state["application_id"], "flags": state["flags"]})
        return {"review": Review.model_validate(answer).model_dump()}

    def finalize(state: State) -> State:
        rv = Review.model_validate(state["review"])
        app_id = state["application_id"]
        extractions, changes = apply_edits(state["extractions"], rv.edits)
        for c in changes:
            repo.audit(app_id, rv.reviewer, "field_edited", c)
        flags = [{**f, "decision": rv.flag_decisions.get(f["code"], "accept")} for f in state["flags"]]
        status = "approved" if rv.decision == "approve" else "rejected"
        profile = build_profile(app_id, extractions, flags, rv, status)
        repo.update(app_id, status=status, profile=profile)
        repo.audit(app_id, rv.reviewer, status, {"notes": rv.notes, "flag_decisions": rv.flag_decisions})
        log.info("application %s %s by reviewer", app_id, status)
        return {"extractions": extractions, "flags": flags, "status": status, "profile": profile}

    g = StateGraph(State)
    for name, fn in [("extract", extract), ("validate", validate), ("cross_check", cross_check),
                     ("review", review), ("finalize", finalize)]:
        g.add_node(name, fn)
    g.add_edge(START, "extract")
    g.add_edge("extract", "validate")
    g.add_edge("validate", "cross_check")
    g.add_edge("cross_check", "review")
    g.add_edge("review", "finalize")
    g.add_edge("finalize", END)
    return g.compile(checkpointer=checkpointer)


def build_profile(app_id: str, extractions: dict, flags: list[dict], rv: Review, status: str) -> dict:
    d = ok_data(extractions)
    w2, stub, stmt = d.get("w2"), d.get("paystub"), d.get("statement")
    ssn = (w2 or {}).get("ssn")
    return {
        "application_id": app_id,
        "identity": {"name": (w2 or stub or {}).get("employee") or (stmt or {}).get("account_holder"),
                     "ssn_last4": ssn[-4:] if ssn else None},
        "employer": (stub or w2 or {}).get("employer"),
        "verified_income": {"annual_w2_cents": (w2 or {}).get("wages_box1"),
                            "paystub_ytd_cents": (stub or {}).get("ytd_gross"),
                            "net_per_period_cents": (stub or {}).get("net")},
        "bank": {"closing_balance_cents": (stmt or {}).get("closing_balance")},
        "flags": [{k: f[k] for k in ("code", "severity", "message", "decision")} for f in flags],
        "open_flags": sum(f["decision"] == "accept" for f in flags),
        "decision": status, "reviewer": rv.reviewer, "notes": rv.notes,
    }
