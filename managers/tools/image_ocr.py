"""Extract text from images with Tesseract OCR."""

import base64
import io

import pytesseract
import requests
from PIL import Image, ImageOps

from utils.logger import get_logger

logger = get_logger()


def _build_tesseract_config(psm: int | None, oem: int | None) -> str:
    parts = []
    if psm is not None:
        parts.append(f"--psm {psm}")
    if oem is not None:
        parts.append(f"--oem {oem}")
    return " ".join(parts)


def _load_image_bytes(image_path: str | None, image_url: str | None, image_base64: str | None) -> bytes:
    if image_path:
        with open(image_path, "rb") as f:
            return f.read()

    if image_url:
        response = requests.get(image_url, timeout=20)
        response.raise_for_status()
        return response.content

    if image_base64:
        return base64.b64decode(image_base64)

    raise ValueError("Provide one source: image_path, image_url, or image_base64")


async def image_ocr(
    image_path: str = "",
    image_url: str = "",
    image_base64: str = "",
    lang: str = "eng",
    psm: int | None = None,
    oem: int | None = None,
) -> str:
    try:
        raw = _load_image_bytes(image_path, image_url, image_base64)
        image = Image.open(io.BytesIO(raw))

        image = ImageOps.grayscale(image)
        config = _build_tesseract_config(psm, oem)
        text = pytesseract.image_to_string(image, lang=lang, config=config)

        cleaned = text.strip()
        if not cleaned:
            return "No text detected in image."
        return cleaned
    except pytesseract.TesseractNotFoundError:
        logger.error("Tesseract binary not found")
        return "Error: Tesseract OCR is not installed on host (install `tesseract-ocr`)."
    except Exception as exc:
        logger.error("image_ocr failed: %s", exc)
        return f"Error: {exc!s}"
