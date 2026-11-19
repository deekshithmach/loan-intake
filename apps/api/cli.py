"""Usage:
  uv run python -m apps.api.cli extract FILE.pdf [...]
  uv run python -m apps.api.cli eval data/generated --limit 10 [--model NAME]
"""

import argparse
import json
import logging
import sys
import time
from collections import defaultdict
from pathlib import Path

from apps.api.config import ROOT
from apps.api.extraction import Extractor
from apps.api.llm import Usage, get_provider
from evals.compare import group, score

RUNS = ROOT / "data" / "runs"


def cmd_extract(ex: Extractor, args) -> None:
    for f in args.files:
        print(json.dumps(ex.run(f).to_dict(), indent=2, default=str))


def cmd_eval(ex: Extractor, args) -> None:
    dirs = sorted(p.parent for p in Path(args.dir).glob("*/truth.json"))[: args.limit]
    RUNS.mkdir(parents=True, exist_ok=True)
    out = RUNS / f"eval-{time.strftime('%Y%m%d-%H%M%S')}.jsonl"
    hits: dict[tuple, list[bool]] = defaultdict(list)
    total, failed = Usage(), 0
    with out.open("w") as fh:
        for d in dirs:
            truth = json.loads((d / "truth.json").read_text())
            for doc_type, doc in truth["documents"].items():
                r = ex.run(d / doc["file"])
                total += r.usage
                failed += not r.ok
                matched = score(r.data, doc["fields"]) if r.doc_type == doc_type else score(None, doc["fields"])
                wrong = [k for k, ok in matched.items() if not ok]
                for k, ok in matched.items():
                    hits[(doc_type, "scanned" if doc["scanned"] else "clean", group(k))].append(ok)
                rec = {"applicant": d.name, "expected": doc_type, **r.to_dict(), "wrong_fields": wrong}
                fh.write(json.dumps(rec, default=str) + "\n")
                print(f"{d.name} {doc_type:9} {'scan' if doc['scanned'] else 'text'} "
                      f"{'ok ' if r.ok else 'FAIL'} tries={r.attempts} wrong={len(wrong)}", file=sys.stderr)

    print(f"\n{'doc':10}{'kind':9}{'fields':14}{'accuracy':>9}{'n':>6}")
    for (doc, kind, grp), v in sorted(hits.items()):
        print(f"{doc:10}{kind:9}{grp:14}{sum(v) / len(v):>8.1%}{len(v):>6}")
    for kind in ("clean", "scanned"):
        v = [x for (_, k, _), xs in hits.items() if k == kind for x in xs]
        if v:
            print(f"{'ALL':10}{kind:9}{'all':14}{sum(v) / len(v):>8.1%}{len(v):>6}")
    n = len(dirs)
    print(f"\n{n} applicants, {failed} failed docs, {total.calls} LLM calls, "
          f"{total.input_tokens} in / {total.output_tokens} out tokens, ${total.cost_usd:.4f} "
          f"(${total.cost_usd / max(n, 1):.4f}/applicant), {total.latency_ms / 1000:.0f}s LLM time")
    print(f"details: {out.relative_to(ROOT)}")


def main() -> None:
    ap = argparse.ArgumentParser(prog="loan-intake")
    ap.add_argument("--model", help="override LLM_MODEL")
    ap.add_argument("-v", "--verbose", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("extract")
    e.add_argument("files", nargs="+")
    v = sub.add_parser("eval")
    v.add_argument("dir")
    v.add_argument("--limit", type=int, default=10)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(levelname)s %(name)s: %(message)s")
    ex = Extractor(get_provider(model=args.model))
    {"extract": cmd_extract, "eval": cmd_eval}[args.cmd](ex, args)


if __name__ == "__main__":
    main()
