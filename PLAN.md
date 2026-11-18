# Loan Intake Agent — Build Plan

> An agentic workflow that turns messy loan documents (bank statements, pay stubs, W-2s) into a verified applicant profile with risk flags, then hands it to a human underwriter for a decision.
> **All data is synthetic. No real PII.**

---

## 1. Why this project (JD mapping)
| JD requirement | Shown by |
|---|---|
| Agentic workflows for lending/credit | LangGraph intake → verify → review workflow |
| Design evals | Field-level accuracy + flag precision/recall on labeled synthetic set |
| Observability in production | Per-run traces: tokens, cost, latency, step outcomes |
| Prompt/context engineering, small models | Same pipeline run on small vs large model, compared |
| Process orchestration | Graph with branching, retries, human-in-the-loop interrupt |
| Data controls / AI security | PII masking in logs, synthetic data only, audit trail |
| Client-facing | Underwriter UI + 2-min demo video |

## 2. The user story
*Priya, an underwriter, receives a loan application with 3 PDFs. Today she spends ~30 min keying numbers and cross-checking. With the agent, she opens a pre-filled profile, sees 2 flagged issues with evidence, and approves/rejects in 5 min.*

## 3. Scope
**In (MVP):** 3 doc types · extraction to schema · cross-document checks · risk flags with evidence · review UI · eval report · Docker deploy.
**Out (later):** credit bureau pulls, real OCR of handwriting, auth/multi-tenant, decisioning model.

## 4. Architecture
```
[Upload UI (Next.js)] ──> [FastAPI] ──> [LangGraph workflow] ──> [Postgres]
                                              │
        classify → extract → validate → cross-check → flag → (interrupt) human review → finalize
                                              │
                                     [LLM API: small / large]
                                     [Traces → runs table]
```

### Workflow nodes
1. **classify** — which doc type is this? (statement / pay stub / W-2 / unknown)
2. **extract** — PDF → text (pypdf); scanned pages → image sent to a vision model → LLM structured output into Pydantic schema
3. **validate** — deterministic rules per doc (totals add up, dates valid, SSN format, balance math)
4. **cross-check** — across docs: pay stub YTD vs W-2, net pay vs statement deposits, employer name match
5. **flag** — risk flags w/ evidence + severity (NSF/overdrafts, income mismatch, large unexplained deposits, gambling/cash-advance txns)
6. **human review** — LangGraph `interrupt`; underwriter edits fields, accepts/rejects flags
7. **finalize** — write applicant profile + decision + audit log

Low-confidence fields or failed validation → route to review with highlights. Extraction failure → one retry with error fed back, then mark for manual.

## 5. Data (synthetic generator)
- `Faker` → applicant, employer, payroll, 3 months of transactions
- ReportLab draws each document directly to PDF (W-2 drawn to mimic the IRS layout)
- **Noise:** ~30% of docs get rotation/blur/scan artifacts (PyMuPDF + Pillow) → image PDF
- **Planted anomalies** (~40% of applicants): income mismatch, overdrafts, fake employer, altered totals
- Output: `data/applicants/<id>/{*.pdf, truth.json}` → ground truth for evals
- Target: 100 applicants (300 docs)

## 6. Schemas (Pydantic, core fields)
- **PayStub:** employer, employee, pay_period, gross, net, ytd_gross, deductions
- **W2:** employer, EIN, employee, wages_box1, federal_tax_box2, year
- **BankStatement:** bank, account_holder, period, opening/closing balance, transactions[]
- **Flag:** code, severity, message, evidence (doc + field/txn ref)
- **ApplicantProfile:** identity, verified_income, flags[], confidence, status

## 7. Evals
| Metric | Target |
|---|---|
| Field extraction accuracy (exact/normalized) | ≥ 95% clean, ≥ 85% noisy |
| Flag recall / precision (planted anomalies) | ≥ 90% / ≥ 85% |
| Cost per application | report (aim < $0.05) |
| p50 / p95 latency per application | report |
| Small vs large model | same table, both models |

`make eval` → writes `evals/report.md` (committed, linked from README). Runs in CI on a 10-applicant subset.

## 8. Stack
Python 3.11 · `uv` · FastAPI · LangGraph · Gemini (dev) / Claude SDK (final evals) · Pydantic · Postgres (Docker) · pypdf + PyMuPDF · ReportLab + Faker · Next.js + TypeScript · pytest · GitHub Actions · Render/Fly (API) + Vercel (UI)

## 9. Repo layout
```
loan-intake-agent/
  apps/api/            FastAPI + LangGraph workflow
    workflow/          nodes, graph, prompts
    schemas/           Pydantic models
    rules/             validation + cross-check rules
  apps/web/            Next.js review UI
  datagen/             synthetic generator + templates
  evals/               runner, metrics, report.md
  data/                generated (gitignored, small sample committed)
  docker-compose.yml
  README.md            problem, demo GIF, architecture, eval results, tradeoffs
```

## 10. Milestones — 1-week sprint (LOCKED)
| Day | Branch | Done when |
|---|---|---|
| 1 | `feature-dev/datagen` | Env ready; 1 sample applicant reviewed by user → then 100 applicants + truth.json |
| 2 | `feature-dev/extraction` | Schemas + LLM extraction CLI (`pdf → JSON`); first field-accuracy number |
| 3 | `feature-dev/workflow` | Rules, cross-checks, flags, LangGraph graph w/ interrupt, FastAPI + Postgres |
| 4 | `feature-dev/review-ui` | Next.js upload + underwriter review screen wired to API |
| 5 | `feature-dev/evals` | Eval runner, traces (cost/latency), small vs large model table |
| 6 | `improvement/deploy-docs` | Live URL, README w/ results, demo video |
| 7 | buffer | Fixes + LinkedIn post |

Evals run on a 30-applicant subset (all 100 only for the final report). Commit daily; PR per branch.

## 11. Interview story (fill in with real numbers)
- "Underwriter intake took ~30 min; my agent gets it to ~5 min at X% field accuracy."
- "Hardest problem: ____ (e.g., scanned statements). I fixed it by ____."
- "Haiku with better context hit X% vs Sonnet's Y% at 1/Z the cost."
- "I keep humans in the loop for anything below confidence threshold — here's why."

## 12. Decisions (LOCKED 2026-11-18)
1. **LLM:** provider-agnostic interface. Dev on Gemini Flash free tier; final evals on Claude Haiku (+ Sonnet comparison); optional Ollama 3B as small-model baseline. LLM used only for: extraction (main), fallback classification, ambiguous transaction categorization, underwriter summary.
2. **PDFs:** pure Python — ReportLab (generate), PyMuPDF (scan noise + page images). No browser.
3. **Scanned docs:** send page images to a vision-capable model instead of local OCR (no tesseract install).
4. **Frontend:** Next.js + TypeScript from day 1.
5. **Git:** repo `loan-intake`, default branch `develop/loan-intake`; branches `feature-dev/<name>`, `bug-fix/<name>`, `improvement/<name>`; merge via PR only.
6. **Timeline:** 1 week (section 10).
