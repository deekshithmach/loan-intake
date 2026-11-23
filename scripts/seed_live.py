"""Upload a few synthetic applicants to a running API so a live demo isn't empty.

    uv run python scripts/seed_live.py --api https://ledgerly-api.fly.dev

Generates 10 applicants locally (datagen, seed 777, deterministic), then uploads 2 that contain planted
anomalies and 2 clean ones. Synthetic data only.
"""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import httpx

FILES = ("paystub.pdf", "w2.pdf", "statement.pdf")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", required=True, help="API base URL, e.g. https://ledgerly-api.fly.dev")
    ap.add_argument("--flagged", type=int, default=2)
    ap.add_argument("--clean", type=int, default=2)
    a = ap.parse_args()
    api = a.api.rstrip("/")

    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run([sys.executable, "-m", "datagen.generate", "--n", "10", "--seed", "777", "--out", tmp],
                       check=True, stdout=subprocess.DEVNULL)
        dirs = sorted(p.parent for p in Path(tmp).glob("*/truth.json"))
        truth = {d: json.loads((d / "truth.json").read_text()) for d in dirs}
        flagged = [d for d in dirs if truth[d]["expected_flags"]][: a.flagged]
        clean = [d for d in dirs if not truth[d]["expected_flags"]][: a.clean]

        with httpx.Client(timeout=120) as c:
            for d in flagged + clean:
                files = [("files", (f, (d / f).read_bytes(), "application/pdf")) for f in FILES]
                r = c.post(f"{api}/applications", files=files)
                r.raise_for_status()
                print(f"{d.name}: {r.json()['id']} (expected flags: {truth[d]['expected_flags'] or 'none'})")


if __name__ == "__main__":
    main()
