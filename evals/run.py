"""Eval runner.  uv run python -m evals.run --model gemini-3.5-flash-lite --variant both --n 30
Variants: clean (text PDFs) and noisy (every document a heavy-noise scan), same applicants in both.
Writes evals/results/<model>__<variant>.json; `--report` rebuilds evals/report.md from all results.
"""

import argparse
import json
import re
import sys
import time
from collections import defaultdict

from apps.api.config import ROOT
from apps.api.extraction import Extractor
from apps.api.llm import get_provider
from apps.api.rules import Docs, run_rules
from evals.compare import group, score
from evals.metrics import flag_scores, pct, percentile
from evals.recorder import BudgetExceeded, RecordingProvider

DATA = ROOT / "data" / "eval"
RESULTS = ROOT / "evals" / "results"
BASELINE = ROOT / "evals" / "baseline.json"
TARGETS = {"clean": 0.95, "noisy": 0.85, "recall": 0.90, "precision": 0.85}
_IDX = re.compile(r"\.\d+\.")


def evaluate(model: str, variant: str, n: int, rec: RecordingProvider) -> dict:
    ex = Extractor(rec)
    dirs = sorted(p.parent for p in (DATA / variant).glob("*/truth.json"))[:n]
    if not dirs:
        sys.exit(f"no data in {DATA / variant}; run `make eval-data`")
    hits: dict[tuple, list[bool]] = defaultdict(list)
    wrong: dict[str, int] = defaultdict(int)
    pairs, costs, lats, toks = [], [], [], []
    failed = misclassified = docs = attempts = 0
    for d in dirs:
        truth = json.loads((d / "truth.json").read_text())
        extracted, cost, lat, tok = {}, 0.0, 0.0, 0
        for doc_type, doc in truth["documents"].items():
            rec.use(f"{d.name}/{doc['file']}")
            r = ex.run(d / doc["file"])
            docs += 1
            attempts += r.attempts
            failed += not r.ok
            cost += r.usage.cost_usd
            lat += r.usage.latency_ms
            tok += r.usage.input_tokens + r.usage.output_tokens
            right_type = r.doc_type.value == doc_type
            misclassified += not right_type
            if r.ok and right_type:
                extracted[doc_type] = r.data
            for k, ok in score(r.data if right_type else None, doc["fields"]).items():
                hits[(doc_type, group(k))].append(ok)
                if not ok:
                    wrong[f"{doc_type}.{_IDX.sub('.*.', k)}"] += 1
        got = {f.code for f in run_rules(Docs.from_data(extracted))}
        pairs.append((set(truth["expected_flags"]), got))
        costs.append(cost)
        lats.append(lat)
        toks.append(tok)
        rec.save()  # after every applicant, so a crash loses nothing
        print(f"  {d.name} flags expected={sorted(pairs[-1][0])} got={sorted(got)} ${cost:.4f}", file=sys.stderr)
    allv = [x for v in hits.values() for x in v]
    return {
        "model": model, "variant": variant, "n": len(dirs), "docs": docs, "failed_docs": failed,
        "misclassified": misclassified, "avg_attempts": attempts / docs, "fields": len(allv),
        "accuracy": pct(allv),
        "accuracy_by_doc": {t: pct([x for (dt, _), v in hits.items() if dt == t for x in v]) for t in sorted({k[0] for k in hits})},
        "accuracy_by_group": {g: pct([x for (_, gg), v in hits.items() if gg == g for x in v]) for g in ("header", "transactions")},
        "flags": flag_scores(pairs),
        "cost_per_app": sum(costs) / len(costs), "total_cost": sum(costs),
        "latency_p50_s": percentile(lats, 0.5) / 1000, "latency_p95_s": percentile(lats, 0.95) / 1000,
        "tokens_per_app": sum(toks) / len(toks),
        "top_wrong_fields": dict(sorted(wrong.items(), key=lambda kv: -kv[1])[:12]),
        "recorded": time.strftime("%Y-%m-%d"),
    }


def gate(results: list[dict]) -> list[str]:
    fails = []
    base = json.loads(BASELINE.read_text()) if BASELINE.exists() else {}
    for r in results:
        tag, f = f"{r['model']}/{r['variant']}", r["flags"]["overall"]
        if r["accuracy"] < TARGETS[r["variant"]]:
            fails.append(f"{tag}: accuracy {r['accuracy']:.1%} < target {TARGETS[r['variant']]:.0%}")
        if f["recall"] is not None and f["recall"] < TARGETS["recall"]:
            fails.append(f"{tag}: flag recall {f['recall']:.1%} < {TARGETS['recall']:.0%}")
        # noisy precision is tracked against the baseline, not an absolute target: misread scans raise false alarms by design
        if r["variant"] == "clean" and f["precision"] is not None and f["precision"] < TARGETS["precision"]:
            fails.append(f"{tag}: flag precision {f['precision']:.1%} < {TARGETS['precision']:.0%}")
        b = base.get(tag)
        if b and r["accuracy"] < b["accuracy"] - 0.005:
            fails.append(f"{tag}: REGRESSION accuracy {r['accuracy']:.1%} vs baseline {b['accuracy']:.1%}")
        if b and f["recall"] is not None and b["recall"] is not None and f["recall"] < b["recall"] - 0.005:
            fails.append(f"{tag}: REGRESSION flag recall {f['recall']:.1%} vs baseline {b['recall']:.1%}")
        if b and f["precision"] is not None and b.get("precision") is not None and f["precision"] < b["precision"] - 0.005:
            fails.append(f"{tag}: REGRESSION flag precision {f['precision']:.1%} vs baseline {b['precision']:.1%}")
    return fails


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", action="append", help="repeatable; default gemini-3.5-flash-lite")
    ap.add_argument("--variant", choices=["clean", "noisy", "both"], default="both")
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--offline", action="store_true", help="replay recordings only; never call an API (CI)")
    ap.add_argument("--budget", type=float, default=1.0, help="max USD of live API spend for this invocation")
    ap.add_argument("--rerecord", action="store_true")
    ap.add_argument("--gate", action="store_true", help="exit 1 if targets or baseline are missed")
    ap.add_argument("--update-baseline", action="store_true")
    ap.add_argument("--report", action="store_true", help="only rebuild evals/report.md from saved results")
    a = ap.parse_args()
    if a.report:
        from evals.report import build

        return build()
    RESULTS.mkdir(parents=True, exist_ok=True)
    out, spent = [], 0.0
    for model in a.model or ["gemini-3.5-flash-lite"]:
        for variant in ["clean", "noisy"] if a.variant == "both" else [a.variant]:
            inner = None if a.offline else get_provider(model=model)
            rec = RecordingProvider(inner, model, variant, offline=a.offline, budget_usd=a.budget - spent, rerecord=a.rerecord)
            print(f"== {model} {variant} n={a.n}", file=sys.stderr)
            try:
                r = evaluate(model, variant, a.n, rec)
            except BudgetExceeded as e:
                rec.save()
                sys.exit(f"STOPPED: {e}. Progress is saved; re-run (with a higher --budget) to continue.")
            finally:
                spent += rec.spent
            if not a.gate:  # gate runs (CI uses a 10-applicant subset) must not overwrite the committed full results
                (RESULTS / f"{model}__{variant}.json").write_text(json.dumps(r, indent=2))
            out.append(r)
            f = r["flags"]["overall"]
            print(f"{model:24}{variant:6} acc={r['accuracy']:.1%} failed={r['failed_docs']} flag R={f['recall']} P={f['precision']} "
                  f"${r['cost_per_app']:.4f}/app p50={r['latency_p50_s']:.1f}s live_calls={rec.live_calls} replayed={rec.replayed}")
    print(f"live spend this run: ${spent:.4f}")
    if a.update_baseline:
        BASELINE.write_text(json.dumps(
            {f"{r['model']}/{r['variant']}": {"accuracy": r["accuracy"], "recall": r["flags"]["overall"]["recall"],
                                                  "precision": r["flags"]["overall"]["precision"]} for r in out},
            indent=2))
    if a.gate:
        fails = gate(out)
        print("\n".join(["GATE FAILED:", *fails]) if fails else "GATE PASSED")
        sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
