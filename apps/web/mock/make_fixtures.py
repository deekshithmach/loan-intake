"""Build UI-only fixtures from synthetic ground truth (no DB, no LLM, no API).
Run once:  PYTHONPATH=. uv run python apps/web/mock/make_fixtures.py   (needs data/eval/clean; see `make eval-data`)"""
import glob
import json
import shutil
from pathlib import Path

from apps.api.rules import Docs, run_rules

OUT = Path(__file__).parent / "fixtures"
SRC = Path("data/eval/clean")
USAGE = {"calls": 1, "input_tokens": 1800, "output_tokens": 400, "latency_ms": 2100.0, "cost_usd": 0.0021}


def build(dirp: Path, status: str, i: int):
    t = json.loads((dirp / "truth.json").read_text())
    data = {k: d["fields"] for k, d in t["documents"].items()}
    flags = [f.model_dump(mode="json") for f in run_rules(Docs.from_data(data))]
    aid = f"mock-{i:04d}-{dirp.name.lower()}"
    (OUT / aid).mkdir(parents=True, exist_ok=True)
    ex = {}
    for k, d in t["documents"].items():
        shutil.copy(dirp / d["file"], OUT / aid / d["file"])
        ex[k] = {"file": d["file"], "doc_type": k, "scanned": False, "classified_by": "text", "ok": True,
                 "data": d["fields"], "error": None, "attempts": 1, "usage": USAGE}
    name = data["paystub"]["employee"]
    s = {"id": aid, "status": status, "applicant_name": name, "flag_count": len(flags),
         "created_at": f"2026-11-2{i}T09:00:00Z", "updated_at": f"2026-11-2{i}T09:01:00Z", "profile": None}
    return aid, s, {**s, "awaiting_review": status == "in_review", "extractions": ex, "flags": flags}


dirs = sorted(Path(p).parent for p in glob.glob(str(SRC / "*/truth.json")))
flagged = [d for d in dirs if json.loads((d / "truth.json").read_text())["expected_flags"]]
clean = [d for d in dirs if d not in flagged]
picks = [(flagged[0], "in_review"), (flagged[1], "in_review"), (clean[0], "in_review"), (clean[1], "approved"), (flagged[2], "rejected")]
OUT.mkdir(parents=True, exist_ok=True)
summaries, details = [], {}
for i, (d, st) in enumerate(picks, 1):
    aid, s, det = build(d, st, i)
    summaries.append(s); details[aid] = det
(OUT / "db.json").write_text(json.dumps({"list": summaries[::-1], "details": details}, indent=1))
print("fixtures:", [s["applicant_name"] + "/" + s["status"] for s in summaries])
