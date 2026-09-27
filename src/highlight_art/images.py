"""Image conversion, OCR, and exact-text validation."""
from __future__ import annotations

import hashlib
import io
import shutil
import subprocess
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps


@dataclass(frozen=True)
class ImageValidation:
    ok: bool
    expected: str
    observed: str
    reason: str
    image_sha256: str = ""
    ocr_language: str = ""
    ocr_psm: int = 11


def normalize_ocr(value: str) -> str:
    return " ".join(unicodedata.normalize("NFC", value).split())


def to_kindle_png(payload: bytes, width: int, height: int) -> bytes:
    with Image.open(io.BytesIO(payload)) as source:
        source.load()
        rgba = source.convert("RGBA")
        backdrop = Image.new("RGBA", rgba.size, "white")
        rgb = Image.alpha_composite(backdrop, rgba).convert("RGB")
    contained = ImageOps.contain(rgb, (width, height), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (width, height), "white")
    offset = ((width - contained.width) // 2, (height - contained.height) // 2)
    canvas.paste(contained, offset)
    gray = canvas.convert("L")
    indexed = Image.frombytes("P", gray.size, gray.tobytes())
    indexed.putpalette([channel for value in range(256) for channel in (value, value, value)])
    output = io.BytesIO()
    indexed.save(output, format="PNG", optimize=True)
    return output.getvalue()


def inspect_kindle_png(payload: bytes, width: int, height: int) -> tuple[bool, str]:
    try:
        with Image.open(io.BytesIO(payload)) as image:
            image.load()
            if image.format != "PNG":
                return False, "not a PNG"
            if image.size != (width, height):
                return False, f"unexpected dimensions {image.size}"
            if image.mode != "P":
                return False, f"unexpected mode {image.mode}; expected PNG8 palette"
            if "icc_profile" in image.info:
                return False, "embedded ICC profile"
            if "transparency" in image.info:
                return False, "unexpected transparency"
    except OSError as exc:
        return False, f"invalid image: {exc}"
    return True, "ok"


def check_ocr(languages: str = "eng") -> None:
    if not shutil.which("tesseract"):
        raise RuntimeError("Install Tesseract before generation")
    result = subprocess.run(["tesseract", "--list-langs"], capture_output=True, text=True, check=True)
    available = set(result.stdout.splitlines())
    missing = set(languages.split("+")) - available
    if missing:
        raise RuntimeError("Missing Tesseract languages: " + ", ".join(sorted(missing)))


def run_tesseract(payload: bytes, *, executable: str = "tesseract", languages: str = "eng", psm: int = 11) -> str:
    with tempfile.NamedTemporaryFile(suffix=".png") as temporary:
        temporary.write(payload)
        temporary.flush()
        result = subprocess.run(
            [executable, temporary.name, "stdout", "--psm", str(psm), "-l", languages],
            check=False,
            capture_output=True,
            timeout=45,
            text=True,
        )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "tesseract failed")
    return result.stdout.strip()


def validate_exact_quote(payload: bytes, quote: str, width: int, height: int, *, languages: str = "eng") -> ImageValidation:
    format_ok, reason = inspect_kindle_png(payload, width, height)
    if not format_ok:
        return ImageValidation(False, normalize_ocr(quote), "", reason)
    observed = run_tesseract(payload) if languages == "eng" else run_tesseract(payload, languages=languages)
    expected_normalized = normalize_ocr(quote)
    observed_normalized = normalize_ocr(observed)
    matched_language, matched_mode = languages, 11
    if observed_normalized != expected_normalized:
        strategies = [(lang, mode) for lang in dict.fromkeys([languages, *languages.split("+")])
                      for mode in (3, 6, 11) if (lang, mode) != (languages, 11)]
        for lang, mode in strategies:
            alternative = run_tesseract(payload, languages=lang, psm=mode)
            if normalize_ocr(alternative) == expected_normalized:
                observed_normalized = normalize_ocr(alternative)
                matched_language, matched_mode = lang, mode
                break
    if observed_normalized != expected_normalized:
        return ImageValidation(False, expected_normalized, observed_normalized, "OCR text does not exactly match")
    return ImageValidation(
        True,
        expected_normalized,
        observed_normalized,
        "ok",
        hashlib.sha256(payload).hexdigest(),
        ocr_language=matched_language, ocr_psm=matched_mode,
    )
