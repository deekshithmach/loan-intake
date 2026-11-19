"""Turn a text PDF into an image-only 'scan': rotate, blur, noise, JPEG, no text layer."""
import io
import random
from pathlib import Path

import pymupdf
from PIL import Image, ImageFilter


def scanify(path: Path, rng: random.Random, dpi: int = 130) -> None:
    src = pymupdf.open(path)
    out = pymupdf.open()
    for page in src:
        pix = page.get_pixmap(dpi=dpi)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        img = img.rotate(rng.uniform(-2.5, 2.5), resample=Image.BICUBIC, fillcolor=(250, 250, 248))
        img = img.filter(ImageFilter.GaussianBlur(rng.uniform(0.5, 1.1)))
        noise = Image.effect_noise(img.size, rng.uniform(10, 22)).convert("RGB")
        img = Image.blend(img, noise, 0.08)
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=rng.randint(45, 70))
        new = out.new_page(width=page.rect.width, height=page.rect.height)
        new.insert_image(new.rect, stream=buf.getvalue())
    src.close()
    out.save(path)  # new_page-built doc, so saving to the original path is safe once src is closed
    out.close()
