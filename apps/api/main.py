"""FastAPI app. Run: uv run uvicorn apps.api.main:app --reload"""

import logging
import re
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any

from fastapi import BackgroundTasks, FastAPI, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from langgraph.types import Command

from .config import ROOT, Settings
from .llm.registry import listing
from .pii import setup_logging
from .repo import Repo
from .stats import summarize
from .workflow import Review, apply_edits, build_graph

log = logging.getLogger(__name__)
UPLOADS = ROOT / "data" / "uploads"
MAX_BYTES = 10 * 1024 * 1024
_SAFE = re.compile(r"[^A-Za-z0-9._-]")


@dataclass
class Deps:
    repo: Repo
    graph: Any  # compiled LangGraph
    uploads: Path = UPLOADS


def _postgres_deps() -> tuple[Deps, Any]:
    from functools import lru_cache

    from langgraph.checkpoint.postgres import PostgresSaver
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool

    from .extraction import Extractor
    from .llm import get_provider
    from .repo import PostgresRepo

    s = Settings()
    pool = ConnectionPool(s.database_url, open=True,
                          kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row})
    saver = PostgresSaver(pool)
    saver.setup()
    repo = PostgresRepo(pool)
    uploads = Path(s.uploads_dir) if s.uploads_dir else UPLOADS
    default = get_provider()

    @lru_cache(maxsize=16)  # one Extractor (and HTTP client) per model, created on first use
    def extractor_for(model: str) -> Extractor:
        return Extractor(get_provider(model=model))

    graph = build_graph(Extractor(default), repo, saver, extractor_for, default.model)
    return Deps(repo, graph, uploads), pool


def create_app(deps: Deps | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        setup_logging()
        pool = None
        if deps is None:
            app.state.deps, pool = _postgres_deps()
        else:
            app.state.deps = deps
        yield
        if pool:
            pool.close()

    app = FastAPI(title="Loan Intake", lifespan=lifespan)
    origins = [o.strip().rstrip("/") for o in Settings().cors_origins.split(",") if o.strip()]
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_origin_regex=Settings().cors_origin_regex or None,
                       allow_methods=["*"], allow_headers=["*"])

    def d() -> Deps:
        return app.state.deps

    def cfg(app_id: str) -> dict:
        return {"configurable": {"thread_id": app_id}}

    def require(app_id: str) -> dict:
        row = d().repo.get(app_id)
        if not row:
            raise HTTPException(404, "application not found")
        return row

    def run_until_review(app_id: str, paths: list[str], model: str | None = None) -> None:
        try:
            state = {"application_id": app_id, "files": paths, **({"model": model} if model else {})}
            d().graph.invoke(state, cfg(app_id))
        except Exception as e:
            log.exception("application %s failed", app_id)
            d().repo.update(app_id, status="failed")
            d().repo.audit(app_id, "system", "failed", {"error": str(e)[:500]})

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.get("/models")
    def models():
        return listing()

    @app.get("/stats")
    def stats():
        """Per-model numbers over every application that has been run (see apps/api/stats.py)."""
        return {"models": summarize(d().repo.recent(1000))}

    @app.post("/applications", status_code=202)
    async def create(files: list[UploadFile], background: BackgroundTasks, model: Annotated[str | None, Form()] = None):
        if not 1 <= len(files) <= 10:
            raise HTTPException(422, "upload 1-10 PDFs")
        if model:
            match = next((m for m in listing() if m["id"] == model), None)
            if not match:
                raise HTTPException(422, f"unknown model '{model}'")
            if not match["available"]:
                raise HTTPException(422, f"model '{model}' is not available (no API key configured)")
        app_id = f"APP-{uuid.uuid4().hex[:8].upper()}"
        folder = d().uploads / app_id
        folder.mkdir(parents=True, exist_ok=True)
        paths = []
        for f in files:
            body = await f.read()
            if not body.startswith(b"%PDF") or len(body) > MAX_BYTES:
                raise HTTPException(422, f"{f.filename}: not a PDF or larger than 10 MB")
            p = folder / _SAFE.sub("_", Path(f.filename or "doc.pdf").name)
            p.write_bytes(body)
            paths.append(str(p))
        d().repo.create(app_id)
        if model:
            d().repo.update(app_id, model=model)
        d().repo.audit(app_id, "applicant", "uploaded", {"files": [Path(p).name for p in paths], "model": model})
        background.add_task(run_until_review, app_id, paths, model)
        return {"id": app_id, "status": "processing"}

    @app.get("/applications")
    def list_apps(limit: int = 100, status: str | None = None):
        """`status` is optional and comma-separated, e.g. `?status=in_review,processing`."""
        wanted = [x.strip() for x in status.split(",") if x.strip()] if status else None
        return d().repo.recent(limit, wanted)

    @app.get("/applications/{app_id}")
    def get_app(app_id: str):
        row = require(app_id)
        st = d().graph.get_state(cfg(app_id))
        v = st.values or {}
        return {**row, "awaiting_review": "review" in (st.next or ()),
                "extractions": v.get("extractions", {}), "flags": v.get("flags", [])}

    @app.post("/applications/{app_id}/review")
    def review(app_id: str, body: Review):
        require(app_id)
        st = d().graph.get_state(cfg(app_id))
        if "review" not in (st.next or ()):
            raise HTTPException(409, "application is not awaiting review")
        try:
            apply_edits(st.values["extractions"], body.edits)  # reject bad edits before resuming
        except ValueError as e:
            raise HTTPException(422, str(e)) from e
        d().repo.audit(app_id, body.reviewer, "review_submitted",
                       {"decision": body.decision, "edited": {k: list(v) for k, v in body.edits.items()}})
        d().graph.invoke(Command(resume=body.model_dump()), cfg(app_id))
        return get_app(app_id)

    @app.get("/applications/{app_id}/audit")
    def audit(app_id: str):
        require(app_id)
        return d().repo.audit_trail(app_id)

    @app.get("/applications/{app_id}/files/{name}")
    def file(app_id: str, name: str):
        require(app_id)
        p = (d().uploads / app_id / name).resolve()
        if p.parent != (d().uploads / app_id).resolve() or not p.is_file():
            raise HTTPException(404, "file not found")
        return FileResponse(p, media_type="application/pdf")

    return app


app = create_app()
