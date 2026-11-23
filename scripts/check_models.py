"""Smoke-test candidate vision LLMs on ONE noisy scanned pay stub before building anything around them.

    uv run python scripts/check_models.py              # every candidate that has a key
    uv run python scripts/check_models.py --only groq  # one candidate

For each model it checks: (1) does the API accept an image, (2) is the reply valid JSON, (3) how many of the
4 fields (employer, employee, gross, net) match the ground truth, plus latency and tokens. About 1 call per
model, so it costs nothing on free tiers. Keys are read from the environment / .env and are never printed.

Add the keys you have to .env (any you leave out are skipped):
    GEMINI_API_KEY (already), MISTRAL_API_KEY, GROQ_API_KEY, OPENROUTER_API_KEY, GITHUB_TOKEN
Override a model name without editing this file:  CHECK_GROQ_MODEL=...  CHECK_MISTRAL_MODEL=...  etc.
Needs data/eval/noisy (run `make eval-data` once). Synthetic data only.
"""

import argparse
import base64
import json
import os
import re
import sys
import time

import httpx
from dotenv import load_dotenv

from apps.api.config import ROOT
from apps.api.extraction.pdf import load_pdf

load_dotenv(ROOT / ".env")

PROMPT = (
    "This is a scanned pay stub. Reply with a single JSON object only, with exactly these keys: "
    '"employer" (string), "employee" (string), "gross" (gross pay for the period as an integer number of cents), '
    '"net" (net pay for the period as an integer number of cents).'
)
FIELDS = ("employer", "employee", "gross", "net")

# name -> (base_url, key env var, default model). Model names change often: override with CHECK_<NAME>_MODEL.
OPENAI_COMPAT = {
    "mistral": ("https://api.mistral.ai/v1", "MISTRAL_API_KEY", "mistral-small-latest"),
    "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY", "meta-llama/llama-4-scout-17b-16e-instruct"),
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY", "google/gemma-3-27b-it:free"),
    "github": ("https://models.github.ai/inference", "GITHUB_TOKEN", "openai/gpt-4.1-mini"),
}
GEMINI_MODELS = ["gemini-3.5-flash-lite", "gemini-3.5-flash"]  # override: CHECK_GEMINI_MODELS=a,b


def parse_json(text: str) -> dict | None:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    try:
        v = json.loads(m.group(0)) if m else None
    except json.JSONDecodeError:
        return None
    return v if isinstance(v, dict) else None


def norm(v) -> str:
    return re.sub(r"\s+", " ", str(v)).strip().lower()


def same(got, want) -> bool:
    if isinstance(want, int | float):  # amounts are integer cents
        try:
            return float(str(got).replace(",", "")) == float(want)
        except ValueError:
            return False
    return norm(got) == norm(want)


def score(got: dict | None, truth: dict) -> int:
    return sum(1 for k in FIELDS if got and k in got and same(got[k], truth[k]))


def call_openai_compat(name: str, png: bytes) -> dict:
    base, key_env, default = OPENAI_COMPAT[name]
    key, model = os.environ[key_env], os.environ.get(f"CHECK_{name.upper()}_MODEL", default)
    body = {"model": model, "temperature": 0, "max_tokens": 600,
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": PROMPT},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(png).decode()}}]}],
            "response_format": {"type": "json_object"}}
    notes = []
    with httpx.Client(timeout=120) as c:
        t0 = time.time()
        r = c.post(f"{base}/chat/completions", json=body, headers={"Authorization": f"Bearer {key}"})
        if r.status_code == 400 and "response_format" in r.text.lower():  # some models reject JSON mode
            body.pop("response_format")
            notes.append("no json_mode")
            r = c.post(f"{base}/chat/completions", json=body, headers={"Authorization": f"Bearer {key}"})
        ms = (time.time() - t0) * 1000
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:160]}")
    j = r.json()
    u = j.get("usage") or {}
    return {"model": model, "text": j["choices"][0]["message"]["content"] or "", "ms": ms,
            "tokens": f"{u.get('prompt_tokens', '?')}/{u.get('completion_tokens', '?')}", "notes": notes}


def call_gemini(model: str, png: bytes) -> dict:
    from apps.api.llm import get_provider

    resp = get_provider(model=model).generate(PROMPT, images=[png], json_mode=True)
    u = resp.usage
    return {"model": model, "text": resp.text, "ms": u.latency_ms, "tokens": f"{u.input_tokens}/{u.output_tokens}", "notes": []}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="gemini | " + " | ".join(OPENAI_COMPAT))
    ap.add_argument("--applicant", default="A0000")
    a = ap.parse_args()

    folder = ROOT / "data" / "eval" / "noisy" / a.applicant
    if not (folder / "truth.json").exists():
        sys.exit(f"no {folder}; run `make eval-data` first")
    truth = json.loads((folder / "truth.json").read_text())["documents"]["paystub"]["fields"]
    png = load_pdf(folder / "paystub.pdf").images[0]
    print(f"test doc: noisy scan {a.applicant}/paystub.pdf, image {len(png) // 1024} KB\n")

    jobs = []  # (label, callable)
    if a.only in (None, "gemini") and os.environ.get("GEMINI_API_KEY"):
        for m in os.environ.get("CHECK_GEMINI_MODELS", ",".join(GEMINI_MODELS)).split(","):
            jobs.append((f"gemini/{m}", lambda m=m: call_gemini(m, png)))
    for name, (_, key_env, _) in OPENAI_COMPAT.items():
        if a.only in (None, name):
            if os.environ.get(key_env):
                jobs.append((name, lambda n=name: call_openai_compat(n, png)))
            elif a.only:
                print(f"{name}: {key_env} not set")

    rows = []
    for label, fn in jobs:
        try:
            r = fn()
            got = parse_json(r["text"])
            rows.append((label, r["model"], "OK" if got else "NOT JSON", f"{score(got, truth)}/4",
                         f"{r['ms'] / 1000:.1f}s", r["tokens"], ", ".join(r["notes"])))
        except Exception as e:  # noqa: BLE001 - report every failure, keep going
            msg = str(e).replace("\n", " ")
            tag = "RATE-LIMITED" if "429" in msg else "FAIL"
            rows.append((label, "-", tag, "-", "-", "-", msg[:110]))
    if not rows:
        sys.exit("no candidates to run: add at least one API key (see the top of this file)")

    head = ("candidate", "model", "reply", "fields", "latency", "tok in/out", "notes")
    w = [max(len(str(x[i])) for x in [head, *rows]) for i in range(len(head))]
    for line in [head, *rows]:
        print("  ".join(str(c).ljust(w[i]) for i, c in enumerate(line)))
    print("\nreply OK + fields 4/4 = usable candidate. A FAIL with 'image' or 'vision' in the notes = no image support.")


if __name__ == "__main__":
    main()
