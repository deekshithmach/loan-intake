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
