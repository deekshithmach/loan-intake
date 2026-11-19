"""Test doubles: an extractor that returns ground truth instead of calling an LLM."""

import json
from pathlib import Path

from apps.api.extraction import ExtractionResult
from apps.api.llm import Usage
from apps.api.schemas import SCHEMAS, DocType

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "data" / "sample"


def truth(applicant: str) -> dict:
    return json.loads((SAMPLE / applicant / "truth.json").read_text())


def applicant_with(code: str | None) -> str:
    """First sample applicant whose expected flags contain `code` (None = a clean one)."""
    for p in sorted(SAMPLE.glob("*/truth.json")):
        flags = json.loads(p.read_text())["expected_flags"]
        if (code in flags) if code else not flags:
            return p.parent.name
    raise LookupError(code)


class TruthExtractor:
    """Maps a file name (paystub.pdf, ...) to that applicant's truth fields."""

    def __init__(self, applicant: str, fail: set[str] = frozenset()):
        self.t = truth(applicant)
        self.fail = fail
        self.calls = 0

    def run(self, path) -> ExtractionResult:
        self.calls += 1
        doc = Path(path).stem
        dt = DocType(doc)
        if doc in self.fail:
            return ExtractionResult(str(path), dt, False, "rules", ok=False, error="boom", attempts=2,
                                    usage=Usage(2, 10, 10, 1.0, 0.0))
        fields = self.t["documents"][doc]["fields"]
        data = SCHEMAS[dt].model_validate(fields).model_dump(mode="json")
        return ExtractionResult(str(path), dt, False, "rules", ok=True, data=data, attempts=1,
                                usage=Usage(1, 100, 50, 5.0, 0.001))
