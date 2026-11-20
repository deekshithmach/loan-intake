"""Build evals/report.md from evals/results/*.json (+ hand-written evals/analysis.md)."""

import json

from apps.api.config import ROOT

RESULTS = ROOT / "evals" / "results"
OUT = ROOT / "evals" / "report.md"
TARGETS = {"clean": 0.95, "noisy": 0.85}


def _p(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.1%}"


def build() -> None:
    rs = [json.loads(p.read_text()) for p in sorted(RESULTS.glob("*.json"))]
    if not rs:
        raise SystemExit("no results; run `make eval` first")
    rs.sort(key=lambda r: (r["variant"], r["cost_per_app"]))
    L = ["# Eval report", "",
         ("Synthetic applicants with ground truth (`truth.json`). The same applicants are rendered twice: "
         "**clean** = text PDFs, **noisy** = every document a heavy-noise scan "
         "(rotation up to 4.5 degrees, blur, grain, JPEG quality 22-40), read through the vision path. "
         "Accuracy is exact match (after whitespace/case normalisation) over every truth field, including every transaction row. "
         "Flag recall/precision compare the rules' output on *extracted* data to the planted anomalies."), "",
         "## Targets", "",
         "| Metric | Target |", "|---|---|",
         "| Field accuracy, clean | >= 95% |", "| Field accuracy, noisy | >= 85% |",
         "| Flag recall / precision | >= 90% / >= 85% |", "", "## Results", "",
         "| Model | Set | Applicants | Field accuracy | Failed docs | Flag recall | Flag precision | Cost / applicant | Latency p50 / p95 (per applicant) | Target met |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rs:
        f = r["flags"]["overall"]
        ok = r["accuracy"] >= TARGETS[r["variant"]] and (f["recall"] or 1) >= 0.90
        prec_ok = (f["precision"] or 1) >= 0.85
        L.append(f"| {r['model']} | {r['variant']} | {r['n']} | {_p(r['accuracy'])} ({r['fields']:,} fields) | "
                 f"{r['failed_docs']}/{r['docs']} | {_p(f['recall'])} | {_p(f['precision'])} | ${r['cost_per_app']:.4f} | "
                 f"{r['latency_p50_s']:.1f}s / {r['latency_p95_s']:.1f}s | {('yes' if prec_ok else 'accuracy + recall; precision missed') if ok else '**no**'} |")
    L += ["", ("Latency is the sum of LLM time over an applicant's three documents (sequential). "
          "Cost = tokens x list price from `apps/api/llm/base.py`."), "", "## Accuracy by document type", "",
          "| Model | Set | Pay stub | W-2 | Bank statement | Header fields | Transaction rows |", "|---|---|---|---|---|---|---|"]
    for r in rs:
        d, g = r["accuracy_by_doc"], r["accuracy_by_group"]
        L.append(f"| {r['model']} | {r['variant']} | {_p(d.get('paystub'))} | {_p(d.get('w2'))} | {_p(d.get('statement'))} | "
                 f"{_p(g['header'])} | {_p(g['transactions'])} |")
    L += ["", "## Flag recall by rule", "", "| Model | Set | " + " | ".join(sorted({c for r in rs for c in r["flags"]["per_code"]})) + " |"]
    codes = sorted({c for r in rs for c in r["flags"]["per_code"]})
    L.append("|---|---|" + "---|" * len(codes))
    for r in rs:
        cells = []
        for c in codes:
            s = r["flags"]["per_code"].get(c)
            cells.append("-" if not s else f"R {_p(s['recall'])} / P {_p(s['precision'])} (fp {s['fp']}, fn {s['fn']})")
        L.append(f"| {r['model']} | {r['variant']} | " + " | ".join(cells) + " |")
    L += ["", "## Most frequent wrong fields", ""]
    for r in rs:
        if r["top_wrong_fields"]:
            L.append(f"**{r['model']} / {r['variant']}**: " + ", ".join(f"`{k}` x{v}" for k, v in list(r["top_wrong_fields"].items())[:8]))
            L.append("")
    analysis = ROOT / "evals" / "analysis.md"
    if analysis.exists():
        L += [analysis.read_text().strip(), ""]
    L += ["## Reproduce", "", "```bash", "make eval-data   # generate the 30 applicants x 2 variants (deterministic, seed 777)",
          "make eval        # replays recordings for free; only missing calls hit the API (capped by --budget)",
          "make eval-ci     # offline replay + gate, what CI runs", "```", "",
          ("Raw model responses are committed in `evals/recordings/`, so every number above can be recomputed without spending anything. "
          "Changing a prompt invalidates the recordings for that file's hash and they are re-recorded on the next `make eval`.")]
    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
