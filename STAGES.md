# Loan Intake — Stage Script

Rules: one branch per stage → PR into `develop/loan-intake` → merge → `/ps-interview-capture`. Next stage starts only when every box is ticked. Merge ≥1 real PR/day (green graph). `/clear` between stages.

Model key (Claude Code, switch via `/model`): **S** = Sonnet, **O** = Opus. App LLM: Gemini free (Stages 2–4), Claude API key (Stage 5, billed to API credit, not plan).

| # | Branch | Model | Build |
|---|---|---|---|
| 0 | `develop/loan-intake` | S | Rename folder→`loan-intake`, git init, uv project, skeleton, README stub, public GitHub repo, default branch |
| 1 | `feature-dev/datagen` | S | Faker profiles, ReportLab pay stub/W-2/statement, truth.json, anomalies, scan noise |
| 2 | `feature-dev/extraction` | O design → S build | Pydantic schemas, provider interface (Gemini), classifier (rules→LLM), extractor (text / vision), CLI |
| 3 | `feature-dev/workflow` | O | Rules, cross-checks, flags, LangGraph + interrupt, FastAPI, Postgres (Docker), audit log |
| 4 | `feature-dev/review-ui` | S | Next.js upload, list, review screen (fields vs PDF, flags, edit/approve); stretch: model picker in UI + per-run tokens/cost/latency (accuracy only on synthetic set w/ truth.json) |
| 5 | `feature-dev/evals` | S (+O for failure analysis) | `make eval`, accuracy/flags/cost/latency, Gemini vs Haiku vs Sonnet, report.md, CI gate |
| 6 | `improvement/deploy-docs` | S | Render/Fly + Vercel, README, diagram, demo video |
| 7 | buffer | S | Fixes, `v1.0.0` release, LinkedIn post |

## Validation gates
**0** [ ] `uv sync` clean [ ] repo live, default branch correct [ ] `.env` not tracked
**1** [x] user eyeballs 1 applicant's 3 PDFs [x] cross-doc numbers consistent [x] anomalies present [x] 100 applicants < 2 min, scans image-only [x] pytest on truth.json math
**2** [x] 1 clean + 1 scanned per type extracted correctly [x] field accuracy on 10 applicants (100%, 2,894 fields, gemini-3.5-flash-lite, $0.013/applicant) [x] bad output → retry → fail gracefully [x] tokens/cost logged
**3** [x] pytest pass+fail per rule [x] API run pauses at review, resumes, persists [x] planted anomalies flagged w/ correct evidence (102/102 truths exact) [x] restart mid-review loses nothing (pytest + live uvicorn restart) [x] PII masked in logs
**4** [ ] browser flow upload→review→approve [ ] edits persist + audited [ ] loading/error states [ ] non-technical demo test
**5** [ ] report w/ real numbers ≥30 applicants [ ] targets (clean ≥95%, noisy ≥85%, flag recall ≥90%) or misses explained [ ] CI green + fails on regression [ ] spend < $10
**6** [ ] live URL works on phone [ ] fresh clone + README → `docker compose up` works [ ] user explains architecture/tradeoffs/failure < 3 min

## Progress
- [x] Stage 0 · [x] 1 · [x] 2 · [x] 3 · [ ] 4 · [ ] 5 · [ ] 6 · [ ] 7
