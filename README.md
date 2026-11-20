# Loan Intake Agent

An agentic workflow that turns messy loan documents (bank statements, pay stubs, W-2s) into a verified applicant profile with risk flags, then hands it to a human underwriter for the final decision.

> **All data is synthetic. No real PII.**

Status: under active development (1-week sprint). See `PLAN.md` and `STAGES.md`.

## Quick start
```
cp .env.example .env   # add your keys
uv sync
```

## Evals
`make eval-data` generates 30 synthetic applicants twice (clean text PDFs / heavy-noise scans, same ground truth); `make eval` scores models on them and rewrites [`evals/report.md`](evals/report.md). Raw model responses are committed, so results replay for free; only missing calls hit the API, capped by `BUDGET`.

| Model (30 applicants unless noted) | Clean | Noisy scans | Flag recall | Cost / applicant |
|---|---|---|---|---|
| Claude Haiku 5.5 | 100% | 98.2% | 100% | $0.0025 / $0.0076 |
| Gemini 3.5 flash-lite | 100% | 96.4% | 100% | $0.0128 / $0.0185 |
| Claude Sonnet 5.5 (10 applicants) | 100% | 99.5% | 100% | $0.0445 / $0.0883 |

Noisy flag precision (68-75% for the small models) is below the 85% target: misread scans cause false alarms that go to human review. Details and failure analysis in the report. CI replays the recordings offline (`make eval-ci`) and fails if accuracy or flag recall/precision drop below the recorded baseline.
