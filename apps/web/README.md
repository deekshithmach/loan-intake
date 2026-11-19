# Loan Intake — Review UI

Next.js 16 (App Router, Tailwind 4). Talks to the FastAPI backend at `NEXT_PUBLIC_API_URL` (default `http://127.0.0.1:8000`).

```bash
# from repo root
docker compose up -d
uv run uvicorn apps.api.main:app --port 8000
# here
npm install
npm run dev          # http://localhost:3000
npx playwright test  # e2e: upload → flags → edit → decide (live LLM, ~1 min)
```

- `/` upload PDFs + application list (auto-refreshes while processing)
- `/applications/[id]` PDF beside extracted fields, flags with clickable evidence, edit/approve/reject, audit trail
