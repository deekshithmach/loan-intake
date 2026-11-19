"""PDF -> text layer, or page images when the PDF is a scan (no text layer)."""

from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

MIN_TEXT_CHARS = 40  # below this we treat the PDF as image-only


@dataclass
class PdfContent:
    path: Path
    text: str
    images: list[bytes] = field(default_factory=list)  # PNGs, only filled for scans

    @property
    def scanned(self) -> bool:
        return len(self.text.strip()) < MIN_TEXT_CHARS


def load_pdf(path: str | Path, dpi: int = 150) -> PdfContent:
    path = Path(path)
    with pymupdf.open(path) as doc:
        content = PdfContent(path, "\n".join(page.get_text() for page in doc))
        if content.scanned:
            content.images = [page.get_pixmap(dpi=dpi).tobytes("png") for page in doc]
    return content
