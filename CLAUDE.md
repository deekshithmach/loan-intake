# Loan Intake — Claude notes
- Follow `STAGES.md` (stage script, model per stage, validation gates) and `PLAN.md` (design). Update the Progress line in STAGES.md when a stage's gate passes.
- At each stage start, tell the user which model to switch to (`/model`) per STAGES.md.
- Git: default branch `develop/loan-intake`; branches `feature-dev/*`, `bug-fix/*`, `improvement/*`; PR-only merges. Remind user to run `/ps-interview-capture` after each merge.
- Never read or print `.env`. Synthetic data only.
- User is token-conscious: brief replies, minimal tool calls.
