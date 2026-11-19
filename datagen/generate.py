"""CLI: uv run python -m datagen.generate --n 100 --out data/generated --seed 42"""
import argparse
import json
import random
from pathlib import Path

from .noise import scanify
from .pdfs import DRAW
from .profiles import build_applicant

SCAN_RATE = 0.3


def generate(n: int, out: Path, seed: int = 42, start: int = 0) -> list[dict]:
    out.mkdir(parents=True, exist_ok=True)
    result = []
    for i in range(start, start + n):
        truth = build_applicant(i, seed)
        rng = random.Random(seed * 7919 + i)
        d = out / truth["applicant_id"]
        d.mkdir(exist_ok=True)
        for kind, doc in truth["documents"].items():
            p = d / doc["file"]
            DRAW[kind](doc["fields"], p)
            if rng.random() < SCAN_RATE:
                scanify(p, rng)
                doc["scanned"] = True
        (d / "truth.json").write_text(json.dumps(truth, indent=2))
        result.append(truth)
    return result


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--out", type=Path, default=Path("data/generated"))
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--start", type=int, default=0, help="first applicant index (to add, not overwrite)")
    a = ap.parse_args()
    res = generate(a.n, a.out, a.seed, a.start)
    print(f"{len(res)} applicants -> {a.out} ({sum(bool(t['anomalies']) for t in res)} with anomalies)")
