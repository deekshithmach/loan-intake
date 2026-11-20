# Eval report

Synthetic applicants with ground truth (`truth.json`). The same applicants are rendered twice: **clean** = text PDFs, **noisy** = every document a heavy-noise scan (rotation up to 4.5 degrees, blur, grain, JPEG quality 22-40), read through the vision path. Accuracy is exact match (after whitespace/case normalisation) over every truth field, including every transaction row. Flag recall/precision compare the rules' output on *extracted* data to the planted anomalies.

## Targets

| Metric | Target |
|---|---|
| Field accuracy, clean | >= 95% |
| Field accuracy, noisy | >= 85% |
| Flag recall / precision | >= 90% / >= 85% |

## Results

| Model | Set | Applicants | Field accuracy | Failed docs | Flag recall | Flag precision | Cost / applicant | Latency p50 / p95 (per applicant) | Target met |
|---|---|---|---|---|---|---|---|---|---|
| claude-haiku-5-5 | clean | 30 | 100.0% (8,674 fields) | 0/90 | 100.0% | 100.0% | $0.0025 | 11.4s / 16.6s | yes |
| gemini-3.5-flash-lite | clean | 30 | 100.0% (8,674 fields) | 0/90 | 100.0% | 100.0% | $0.0128 | 8.9s / 31.7s | yes |
| claude-sonnet-5-5 | clean | 10 | 100.0% (2,894 fields) | 0/30 | 100.0% | 100.0% | $0.0445 | 16.2s / 18.6s | yes |
| claude-haiku-5-5 | noisy | 30 | 98.2% (8,674 fields) | 0/90 | 100.0% | 75.0% | $0.0076 | 35.4s / 48.7s | accuracy + recall; precision missed |
| gemini-3.5-flash-lite | noisy | 30 | 96.4% (8,674 fields) | 0/90 | 100.0% | 67.7% | $0.0185 | 22.6s / 81.0s | accuracy + recall; precision missed |
| claude-sonnet-5-5 | noisy | 10 | 99.5% (2,894 fields) | 0/30 | 100.0% | 100.0% | $0.0883 | 22.7s / 35.7s | yes |

Latency is the sum of LLM time over an applicant's three documents (sequential). Cost = tokens x list price from `apps/api/llm/base.py`.

## Accuracy by document type

| Model | Set | Pay stub | W-2 | Bank statement | Header fields | Transaction rows |
|---|---|---|---|---|---|---|
| claude-haiku-5-5 | clean | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| gemini-3.5-flash-lite | clean | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| claude-sonnet-5-5 | clean | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| claude-haiku-5-5 | noisy | 99.0% | 98.8% | 98.2% | 99.0% | 98.1% |
| gemini-3.5-flash-lite | noisy | 98.7% | 96.4% | 96.3% | 98.2% | 96.2% |
| claude-sonnet-5-5 | noisy | 100.0% | 98.2% | 99.5% | 99.4% | 99.5% |

## Flag recall by rule

| Model | Set | altered_totals | fake_employer | income_mismatch | overdrafts | statement_unreconciled |
|---|---|---|---|---|---|---|
| claude-haiku-5-5 | clean | R 100.0% / P 100.0% (fp 0, fn 0) | R 100.0% / P 100.0% (fp 0, fn 0) | R 100.0% / P 100.0% (fp 0, fn 0) | R 100.0% / P 100.0% (fp 0, fn 0) | - |
| gemini-3.5-flash-lite | clean | R 100.0% / P 100.0% (fp 0, fn 0) | R 100.0% / P 100.0% (fp 0, fn 0) | R 100.0% / P 100.0% (fp 0, fn 0) | R 100.0% / P 100.0% (fp 0, fn 0) | - |
| claude-sonnet-5-5 | clean | R 100.0% / P 100.0% (fp 0, fn 0) | R 100.0% / P 100.0% (fp 0, fn 0) | R 100.0% / P 100.0% (fp 0, fn 0) | R 100.0% / P 100.0% (fp 0, fn 0) | - |
| claude-haiku-5-5 | noisy | R 100.0% / P 83.3% (fp 1, fn 0) | R 100.0% / P 80.0% (fp 1, fn 0) | R 100.0% / P 100.0% (fp 0, fn 0) | R 100.0% / P 100.0% (fp 0, fn 0) | R n/a / P 0.0% (fp 5, fn 0) |
| gemini-3.5-flash-lite | noisy | R 100.0% / P 71.4% (fp 2, fn 0) | R 100.0% / P 57.1% (fp 3, fn 0) | R 100.0% / P 100.0% (fp 0, fn 0) | R 100.0% / P 100.0% (fp 0, fn 0) | R n/a / P 0.0% (fp 5, fn 0) |
| claude-sonnet-5-5 | noisy | R 100.0% / P 100.0% (fp 0, fn 0) | R 100.0% / P 100.0% (fp 0, fn 0) | R 100.0% / P 100.0% (fp 0, fn 0) | R 100.0% / P 100.0% (fp 0, fn 0) | - |

## Most frequent wrong fields

**claude-haiku-5-5 / noisy**: `statement.transactions.*.description` x68, `statement.transactions.*.date` x32, `statement.transactions.*.balance` x23, `statement.transactions.*.amount` x22, `paystub.ytd_gross` x2, `w2.ssn` x2, `paystub.gross` x1, `statement.closing_balance` x1

**gemini-3.5-flash-lite / noisy**: `statement.transactions.*.balance` x99, `statement.transactions.*.date` x93, `statement.transactions.*.amount` x53, `statement.transactions.*.description` x50, `w2.employer` x3, `w2.employee` x3, `paystub.ytd_gross` x2, `w2.ssn` x2

**claude-sonnet-5-5 / noisy**: `statement.transactions.*.date` x12, `w2.ssn` x1, `w2.ein` x1

## Analysis

**Targets.** Clean accuracy (>= 95%) and noisy accuracy (>= 85%) are met by every model with a wide margin, and flag recall is 100% for all of them: every planted anomaly was caught, including on heavy-noise scans. **Flag precision on the noisy set misses the 85% target** (Gemini 68%, Haiku 75%; Sonnet 100% on its 10-applicant subset). Everything else is met.

**Why noisy precision misses.** All false alarms come from a scan being misread, not from the rules misbehaving:

| False flag | What happened |
|---|---|
| `statement_unreconciled` (5 per model on 30 applicants) | A transaction digit was misread, so opening balance + transactions no longer equals the closing balance. |
| `fake_employer` (1-3) | A garbled employer name on the W-2 or pay stub falls below the 0.85 similarity threshold. |
| `altered_totals` (1-2) | A misread gross, net or deduction on the pay stub. |

The system raises these on purpose: a false alarm costs an underwriter a glance at the highlighted field next to the PDF, while a missed forgery costs far more. In the UI each one points at the exact field, so the review is quick.

**What was tried: arithmetic self-check.** If a *scanned* statement does not reconcile, the extractor re-reads it once, told which row breaks the running balance, and keeps the re-read only if it fixes the arithmetic. Before and after on the same noisy 30 applicants:

| Model | Accuracy | `statement_unreconciled` false flags | Flag precision |
|---|---|---|---|
| Haiku 5.5, before | 94.1% | 12 | 60% |
| Haiku 5.5, after | 98.2% | 5 | 75% |
| Gemini 3.5 flash-lite, before | 96.7% | 8 | 64% |
| Gemini 3.5 flash-lite, after | 96.4% | 5 | 68% |

**What was tried and rejected: the same self-check on pay-stub totals.** It lifted precision further but dropped recall to 95%: on one genuinely altered pay stub the model "corrected" the net pay to make the arithmetic work, which erased the fraud signal. A verifier that can hide tampering is worse than a false alarm, so the check is limited to scanned bank statements, and the prompt tells the model never to change a number just to make totals add up. A unit test pins the safe behaviour (a re-read that still does not add up keeps the original values).

**Remaining errors are mostly invisible to arithmetic.**
- *Single-digit date misreads* (`2025-12-05` read as `2025-12-06`): the largest error bucket by count, but no rule depends on a transaction date, so no flag changes.
- *Dropped hyphens* (`GONZALEZ-MALDONADO` read as `GONZALEZ MALDONADO`): strict scoring counts each occurrence as a wrong field, and one applicant with a hyphenated employer accounts for many of them. Rules normalise punctuation, so flags are unaffected.
- *Self-consistent hallucinations*: Gemini once changed an amount and the running balance together (`-36.48` read as `-56.48`), so the statement still reconciles and no automated check can catch it. This is the case for the human review step.

**Model comparison.** Sonnet 5.5 is the most accurate on noise (99.5%, no false flags on its subset) but costs about 11x Haiku per applicant ($0.088 vs $0.0076) and about 5x Gemini. Haiku 5.5 is the cheapest for clean documents ($0.0025/applicant) and has the best accuracy-per-dollar. Gemini 3.5 flash-lite is the fastest per document and free on the free tier, but is the least accurate on noisy scans. Sonnet was run on the first 10 applicants only to stay inside the API budget, so its numbers have wider error bars.

**Limits of this eval.** The documents are synthetic and rendered by one generator, so layout variety is low; the noise model (rotation, blur, grain, JPEG) is a stand-in for real scans, not a substitute. Applicant counts are small (30, Sonnet 10), so a single document moves a percentage point. Accuracy is deliberately strict (exact match on every transaction row), which is why it can read lower than the business-level outcome (flags and decisions).

## Reproduce

```bash
make eval-data   # generate the 30 applicants x 2 variants (deterministic, seed 777)
make eval        # replays recordings for free; only missing calls hit the API (capped by --budget)
make eval-ci     # offline replay + gate, what CI runs
```

Raw model responses are committed in `evals/recordings/`, so every number above can be recomputed without spending anything. Changing a prompt invalidates the recordings for that file's hash and they are re-recorded on the next `make eval`.
