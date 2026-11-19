"""PDF -> validated schema. LLM output is untrusted: validate, retry once with the error, then fail soft."""

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from pydantic import ValidationError

from apps.api.llm import LLMProvider, Usage
from apps.api.schemas import SCHEMAS, DocType

from .classify import classify
from .pdf import PdfContent, load_pdf
from .prompts import RETRY, extract_prompt

log = logging.getLogger(__name__)
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$")


@dataclass
class ExtractionResult:
    file: str
    doc_type: DocType
    scanned: bool
    classified_by: str
    ok: bool
    data: dict | None = None  # model_dump(mode="json"): money in int cents, dates ISO
    error: str | None = None
    attempts: int = 0
    usage: Usage = field(default_factory=Usage)

    def to_dict(self) -> dict:
        return asdict(self)


def parse_json(text: str) -> dict:
    return json.loads(_FENCE.sub("", text.strip()))


class Extractor:
    def __init__(self, provider: LLMProvider, max_attempts: int = 2):
        self.provider = provider
        self.max_attempts = max_attempts

    def run(self, path: str | Path) -> ExtractionResult:
        content = load_pdf(path)
        doc_type, method, usage = classify(content, self.provider)
        result = ExtractionResult(str(path), doc_type, content.scanned, method, ok=False, usage=usage)
        if doc_type is DocType.UNKNOWN:
            result.error = "could not classify document"
            return result
        return self._extract(content, result)

    def _extract(self, content: PdfContent, result: ExtractionResult) -> ExtractionResult:
        schema = SCHEMAS[result.doc_type]
        base = extract_prompt(result.doc_type, None if content.scanned else content.text)
        prompt = base
        for attempt in range(1, self.max_attempts + 1):
            resp = self.provider.generate(prompt, images=content.images)
            result.attempts, result.usage = attempt, result.usage + resp.usage
            log.info("extract %s %s attempt=%d in=%d out=%d cost=$%.5f %.0fms",
                     content.path.name, result.doc_type, attempt, resp.usage.input_tokens,
                     resp.usage.output_tokens, resp.usage.cost_usd, resp.usage.latency_ms)
            try:
                model = schema.model_validate(parse_json(resp.text))
            except (json.JSONDecodeError, ValidationError) as e:
                result.error = _short(e)
                prompt = base + RETRY.format(error=result.error, previous=resp.text[:4000])
                continue
            result.ok, result.error, result.data = True, None, model.model_dump(mode="json")
            return result
        log.warning("extract %s failed after %d attempts: %s", content.path.name, result.attempts, result.error)
        return result


def _short(e: Exception) -> str:
    if isinstance(e, ValidationError):
        return "\n".join(f"{'.'.join(map(str, x['loc'])) or '<root>'}: {x['msg']}" for x in e.errors()[:20])
    return f"invalid JSON: {e}"
