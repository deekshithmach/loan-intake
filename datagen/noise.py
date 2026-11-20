"""Turn a text PDF into an image-only 'scan': rotate, blur, noise, JPEG, no text layer."""
import io
import random
from pathlib import Path

import pymupdf
from PIL import Image, ImageFilter

# level -> (dpi, rotation deg, blur sigma, noise blend, noise sigma, jpeg quality)
LEVELS = {
    "normal": (130, 2.5, (0.5, 1.1), 0.08, (10, 22), (45, 70)),
    "heavy": (96, 4.5, (1.0, 1.7), 0.16, (22, 38), (22, 40)),  # fax/phone-photo quality
}


def scanify(path: Path, rng: random.Random, level: str = "normal") -> None:
    dpi, rot, blur, blend, nsig, jpg = LEVELS[level]
    src = pymupdf.open(path)
    out = pymupdf.open()
    for page in src:
        pix = page.get_pixmap(dpi=dpi)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        img = img.rotate(rng.uniform(-rot, rot), resample=Image.BICUBIC, fillcolor=(250, 250, 248))
        img = img.filter(ImageFilter.GaussianBlur(rng.uniform(*blur)))
        noise = Image.effect_noise(img.size, rng.uniform(*nsig)).convert("RGB")
        img = Image.blend(img, noise, blend)
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=rng.randint(*jpg))
        new = out.new_page(width=page.rect.width, height=page.rect.height)
        new.insert_image(new.rect, stream=buf.getvalue())
    src.close()
    out.save(path)  # new_page-built doc, so saving to the original path is safe once src is closed
    out.close()
