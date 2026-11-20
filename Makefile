.PHONY: eval-data eval eval-ci eval-report test

# 30 applicants x 2 variants (clean text PDFs / heavy-noise scans), same truth in both. Deterministic.
eval-data:
	uv run python -m datagen.generate --n 30 --seed 777 --scan-rate 0 --out data/eval/clean
	uv run python -m datagen.generate --n 30 --seed 777 --scan-rate 1 --noise heavy --out data/eval/noisy

# Replays committed recordings (free); only missing calls hit the API. Cap live spend with BUDGET.
MODELS ?= --model gemini-3.5-flash-lite --model claude-haiku-5-5
BUDGET ?= 1.0
eval:
	uv run python -m evals.run $(MODELS) --n 30 --budget $(BUDGET)
	uv run python -m evals.run --report

# What CI runs: offline (no API, no keys), 10 applicants, fails on missed targets or regression vs evals/baseline.json
eval-ci:
	uv run python -m evals.run --model gemini-3.5-flash-lite --n 10 --offline --gate

eval-report:
	uv run python -m evals.run --report

test:
	uv run pytest -q
