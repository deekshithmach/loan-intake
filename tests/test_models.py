"""Model registry, OpenAI-compatible provider (mocked HTTP), per-run model + stats through the API."""

import base64
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver

from apps.api.config import Settings
from apps.api.llm import factory
from apps.api.llm import openai_compat as oc
from apps.api.llm.openai_compat import OpenAICompatProvider
from apps.api.llm.registry import listing
from apps.api.main import Deps, create_app
from apps.api.repo import InMemoryRepo
from apps.api.workflow import build_graph
from tests.fakes import SAMPLE, TruthExtractor, applicant_with

FILES = ["paystub.pdf", "w2.pdf", "statement.pdf"]


# ---- registry / factory -------------------------------------------------------------------
def test_listing_marks_models_available_only_with_a_key():
    rows = {r["id"]: r for r in listing(Settings(_env_file=None, gemini_api_key="k", groq_api_key="g"))}
    assert rows["gemini-3.5-flash"]["available"] and rows["qwen/qwen3.8-27b"]["available"]
    assert not rows["nvidia/nemotron-3.5-super-vl:free"]["available"] and not rows["claude-haiku-5-5"]["available"]
    assert sum(r["default"] for r in rows.values()) == 1


def test_factory_builds_openai_compat_for_groq_and_openrouter():
    s = Settings(_env_file=None, groq_api_key="g", openrouter_api_key="o")
    p = factory.get_provider(s, model="qwen/qwen3.8-27b")
    assert isinstance(p, OpenAICompatProvider) and p.name == "groq" and p.model == "qwen/qwen3.8-27b"
    assert factory.get_provider(s, model="google/gemma-4-31b-it:free").name == "openrouter"
    with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
        factory.get_provider(Settings(_env_file=None), model="qwen/qwen3.8-27b")
    assert factory.provider_for("gemini-3.5-flash", "x") == "gemini" and factory.provider_for("claude-x", "x") == "anthropic"


# ---- OpenAI-compatible provider (HTTP mocked) ----------------------------------------------
def provider(handler, **kw):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return OpenAICompatProvider("groq", "https://x.test/v1", "secret-key", "m", client=client, **kw)


def ok(text='{"a": 1}'):
    return httpx.Response(200, json={"choices": [{"message": {"content": text}}], "usage": {"prompt_tokens": 7, "completion_tokens": 3}})


def test_sends_image_and_json_mode_and_maps_usage():
    seen = {}

    def handler(req):
        seen["body"], seen["auth"] = json.loads(req.content), req.headers["authorization"]
        return ok()

    r = provider(handler).generate("read it", images=[b"PNGDATA"])
    parts = seen["body"]["messages"][0]["content"]
    assert parts[0]["image_url"]["url"] == "data:image/png;base64," + base64.b64encode(b"PNGDATA").decode()
    assert parts[1] == {"type": "text", "text": "read it"}
    assert seen["body"]["response_format"] == {"type": "json_object"} and seen["auth"] == "Bearer secret-key"
    assert r.text == '{"a": 1}' and (r.usage.input_tokens, r.usage.output_tokens, r.usage.calls) == (7, 3, 1)


def test_falls_back_when_model_rejects_json_mode():
    bodies = []

    def handler(req):
        bodies.append(json.loads(req.content))
        if "response_format" in bodies[-1]:
            return httpx.Response(400, text="response_format is not supported by this model")
        return ok()

    assert provider(handler).generate("p").text == '{"a": 1}'
    assert "response_format" in bodies[0] and "response_format" not in bodies[1]


def test_retries_rate_limits_then_gives_up(monkeypatch):
    monkeypatch.setattr(oc.time, "sleep", lambda s: None)
    calls = []

    def handler(req):
        calls.append(1)
        return httpx.Response(429, text="slow down") if len(calls) < 3 else ok()

    assert provider(handler).generate("p").text == '{"a": 1}' and len(calls) == 3
    calls.clear()
    with pytest.raises(RuntimeError, match="HTTP 429"):
        provider(lambda r: httpx.Response(429, text="no"), max_retries=1).generate("p")


# ---- API: model per application + stats ---------------------------------------------------
@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setitem(Settings.model_config, "env_file", None)  # never read the developer's real .env in tests
    for k in ("GROQ_API_KEY", "OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "LLM_MODEL"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    app_dir = applicant_with("altered_totals")
    repo = InMemoryRepo()
    graph = build_graph(TruthExtractor(app_dir), repo, InMemorySaver(), default_model="default-model")
    with TestClient(create_app(Deps(repo, graph, tmp_path))) as c:
        c.files = [("files", (n, (SAMPLE / app_dir / n).read_bytes(), "application/pdf")) for n in FILES]
        yield c


def test_models_endpoint(client):
    rows = {m["id"]: m for m in client.get("/models").json()}
    assert rows["gemini-3.5-flash"]["available"] and not rows["qwen/qwen3.8-27b"]["available"]


def test_upload_rejects_unknown_or_unavailable_model(client):
    assert client.post("/applications", files=client.files, data={"model": "nope"}).status_code == 422
    r = client.post("/applications", files=client.files, data={"model": "qwen/qwen3.8-27b"})
    assert r.status_code == 422 and "not available" in r.json()["detail"]


def test_chosen_model_is_stored_and_stats_are_recorded(client):
    app_id = client.post("/applications", files=client.files, data={"model": "gemini-3.5-flash"}).json()["id"]
    row = client.get(f"/applications/{app_id}").json()
    assert row["model"] == "gemini-3.5-flash" and row["status"] == "in_review"
    assert row["stats"]["docs_ok"] == 3 and row["stats"]["flags"] == row["flag_count"] > 0
    client.post(f"/applications/{app_id}/review", json={"decision": "approve", "reviewer": "priya",
                "flag_decisions": {"altered_totals": "dismiss"}})
    s = client.get("/stats").json()["models"]
    assert [m["model"] for m in s] == ["gemini-3.5-flash"] and s[0]["runs"] == 1
    stats = client.get(f"/applications/{app_id}").json()["stats"]
    assert stats["decision"] == "approved" and stats["flags_dismissed"] == 1 and stats["edits"] == 0


def test_without_a_model_the_default_is_used(client):
    app_id = client.post("/applications", files=client.files).json()["id"]
    assert client.get(f"/applications/{app_id}").json()["model"] == "default-model"
