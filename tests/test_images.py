import io
import shutil
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont

from highlight_art import images


def source_image(width=900, height=1200):
    image = Image.new("RGB", (width, height), "white")
    output = io.BytesIO()
    image.save(output, format="JPEG")
    return output.getvalue()


def test_conversion_produces_clean_exact_size_png8():
    payload = images.to_kindle_png(source_image(), 1264, 1680)
    assert images.inspect_kindle_png(payload, 1264, 1680) == (True, "ok")
    with Image.open(io.BytesIO(payload)) as image:
        assert image.mode == "P"
        assert image.size == (1264, 1680)
        assert "icc_profile" not in image.info


def test_exact_quote_validation_rejects_any_text_change(monkeypatch):
    payload = images.to_kindle_png(source_image(), 1264, 1680)
    monkeypatch.setattr(images, "run_tesseract", lambda *a, **k: "Every word survive.")
    result = images.validate_exact_quote(payload, "Every word survives.", 1264, 1680)
    assert result.ok is False
    assert result.reason == "OCR text does not exactly match"


def test_exact_quote_validation_allows_only_whitespace_layout_changes(monkeypatch):
    payload = images.to_kindle_png(source_image(), 1264, 1680)
    monkeypatch.setattr(images, "run_tesseract", lambda *a, **k: "Every\nword   survives.")
    result = images.validate_exact_quote(payload, "Every word survives.", 1264, 1680)
    assert result.ok is True


FONT = next((path for path in (
    Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
) if path.exists()), None)


@pytest.mark.skipif(not shutil.which("tesseract") or FONT is None, reason="requires a test font and Tesseract")
def test_real_tesseract_round_trip_accepts_exact_final_png():
    quote = "Every word survives."
    canvas = Image.new("RGB", (1264, 1680), "white")
    font = ImageFont.truetype(str(FONT), 64)
    ImageDraw.Draw(canvas).text((100, 700), quote, font=font, fill="black")
    source = io.BytesIO()
    canvas.save(source, format="PNG")
    payload = images.to_kindle_png(source.getvalue(), 1264, 1680)
    assert images.validate_exact_quote(payload, quote, 1264, 1680).ok is True


def test_transparency_composites_onto_white():
    source = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    buffer = io.BytesIO()
    source.save(buffer, format="PNG")
    result = images.to_kindle_png(buffer.getvalue(), 64, 64)
    with Image.open(io.BytesIO(result)) as converted:
        assert converted.convert("RGB").getpixel((32, 32)) == (255, 255, 255)


def test_alternative_layout_must_still_match_every_word(monkeypatch):
    payload = images.to_kindle_png(source_image(), 1264, 1680)
    monkeypatch.setattr(images, "run_tesseract", lambda *a, **k: "Every word survives." if k.get("psm") == 3 else "Every word survive.")
    assert images.validate_exact_quote(payload, "Every word survives.", 1264, 1680).ok
