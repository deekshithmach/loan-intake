"""Doc type: cheap keyword rules first, LLM only when rules can't decide (e.g. scans)."""

import json

from apps.api.llm import LLMProvider, Usage
from apps.api.schemas import DocType

from .pdf import PdfContent
from .prompts import CLASSIFY

KEYWORDS: dict[DocType, tuple[str, ...]] = {
    DocType.W2: ("wage and tax statement", "form w-2", "employer identification"),
    DocType.PAYSTUB: ("earnings statement", "net pay", "pay period"),
    DocType.STATEMENT: ("statement period", "opening balance", "closing balance"),
}


def classify_rules(text: str) -> DocType | None:
    low = text.lower()
    scores = {t: sum(k in low for k in kws) for t, kws in KEYWORDS.items()}
    best = max(scores, key=scores.get)
    ranked = sorted(scores.values(), reverse=True)
    return best if ranked[0] > 0 and ranked[0] > ranked[1] else None  # ties are ambiguous


def classify(content: PdfContent, provider: LLMProvider) -> tuple[DocType, str, Usage]:
    """Returns (doc_type, method, usage) where method is "rules" or "llm"."""
    if not content.scanned and (hit := classify_rules(content.text)):
        return hit, "rules", Usage()
    prompt = CLASSIFY if content.scanned else f"{CLASSIFY}\nDocument text:\n{content.text[:3000]}"
    resp = provider.generate(prompt, images=content.images[:1])
    try:
        return DocType(json.loads(resp.text)["doc_type"]), "llm", resp.usage
    except (ValueError, KeyError, TypeError):
        return DocType.UNKNOWN, "llm", resp.usage
