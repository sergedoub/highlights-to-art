import io
from dataclasses import replace
from datetime import datetime
from pathlib import Path

import pytest
from PIL import Image

from highlight_art.config import load_config
from highlight_art.images import ImageValidation
from highlight_art.models import Highlight
from highlight_art.providers import GeneratedImage
from highlight_art.selection import highlight_date, newest_highlights
from highlight_art.store import Store
from highlight_art.workflow import latest_run


def row(index, date, text="Exact words."):
    return Highlight(f"{index:024x}", "kindle-clippings", "A made-up book", "A. Author", str(index), date, text)


def test_latest_dates_not_lexicographic_or_length_and_deduplicated():
    older = row(1, "Sunday, July 19, 2026 10:20:53 PM", "Short.")
    newer = row(2, "Monday, July 27, 2026 10:03:32 PM", "A much longer quote.")
    duplicate = replace(older, highlighted_at="Tuesday, July 28, 2026 1:00:00 AM")
    assert newest_highlights([older, newer, duplicate], 2) == [duplicate, newer]
    assert highlight_date("Monday, January 1, 2024 12:00:00 AM") == datetime(2024, 1, 1)
    assert highlight_date("Monday, January 1, 2024 12:00:00 PM").hour == 12
    with pytest.raises(ValueError):
        newest_highlights([replace(older, highlighted_at="unknown")])


def config(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "fake-key")
    root = Path(__file__).resolve().parents[1]
    text = (root / "config.example.toml").read_text()
    text = text.replace('"prompts/system.md"', f'"{root}/prompts/system.md"').replace('"prompts/image.md"', f'"{root}/prompts/image.md"')
    path = tmp_path / "config.toml"
    path.write_text(text)
    return load_config(path)


class FakeProvider:
    def __init__(self):
        self.calls = 0

    def generate(self, prompt, model):
        self.calls += 1
        image = Image.new("RGB", (400, 600), "white")
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        return GeneratedImage(buf.getvalue())


def test_workflow_saves_rejected_images_and_resumes_without_paid_calls(tmp_path, monkeypatch):
    cfg = config(tmp_path, monkeypatch)
    provider = FakeProvider()
    monkeypatch.setattr("highlight_art.images.check_ocr", lambda _: None)
    monkeypatch.setattr("highlight_art.workflow.validate_exact_quote", lambda *a, **k: ImageValidation(False, "Exact words.", "Wrong words.", "mismatch"))
    rows = [row(i, f"2026-01-{i:02}T12:00:00") for i in range(1, 7)]
    result = latest_run(cfg, rows, count=5, generate=True, client=provider)
    assert [r["id"] for r in result["selected"]] == [f"{i:024x}" for i in range(6, 1, -1)]
    assert result["api_calls"] == provider.calls == 5
    assert result["generated_images"] == 5
    assert result["validated_images"] == result["active_backgrounds"] == 0
    assert all(Path(r["image_path"]).is_file() for r in result["results"])
    repeated = latest_run(cfg, rows, count=5, generate=True, client=provider)
    assert repeated["api_calls"] == 0
    assert provider.calls == 5
    assert not repeated["complete"]


def test_failed_call_cached_and_explicit_retry_and_budget(tmp_path, monkeypatch):
    cfg = config(tmp_path, monkeypatch)
    cfg = replace(cfg, generation=replace(cfg.generation, max_api_calls_per_run=1))
    monkeypatch.setattr("highlight_art.images.check_ocr", lambda _: None)
    class Failure:
        def generate(self, *args):
            raise RuntimeError("provider echoed SECRET")
    rows = [row(i, f"2026-01-{i:02}T00:00:00") for i in (1, 2)]
    result = latest_run(cfg, rows, count=2, generate=True, client=Failure())
    assert [r["status"] for r in result["results"]] == ["failed", "budget_exhausted"]
    assert "SECRET" not in str(result)
    assert latest_run(cfg, rows[:1], count=1, generate=True, client=Failure())["api_calls"] == 1
    assert latest_run(cfg, rows[:1], count=1, generate=True, client=Failure())["api_calls"] == 0
    assert latest_run(cfg, rows[:1], count=1, generate=True, retry=True, client=Failure())["api_calls"] == 1


def test_success_publishes_only_validated_and_ocr_preflight_precedes_spending(tmp_path, monkeypatch):
    import hashlib
    cfg = config(tmp_path, monkeypatch)
    provider = FakeProvider()
    def fail(_):
        raise RuntimeError("Missing OCR")
    monkeypatch.setattr("highlight_art.images.check_ocr", fail)
    rows = [row(1, "2026-01-01T00:00:00")]
    with pytest.raises(RuntimeError):
        latest_run(cfg, rows, generate=True, client=provider)
    assert provider.calls == 0
    monkeypatch.setattr("highlight_art.images.check_ocr", lambda _: None)
    monkeypatch.setattr("highlight_art.workflow.validate_exact_quote", lambda image, *a, **k: ImageValidation(True, "Exact words.", "Exact words.", "ok", hashlib.sha256(image).hexdigest()))
    result = latest_run(cfg, rows, generate=True, client=provider)
    assert result["complete"]
    assert result["active_backgrounds"] == 1


def test_cache_detects_missing_output_without_spending(tmp_path, monkeypatch):
    cfg = config(tmp_path, monkeypatch)
    provider = FakeProvider()
    monkeypatch.setattr("highlight_art.images.check_ocr", lambda _: None)
    monkeypatch.setattr("highlight_art.workflow.validate_exact_quote", lambda *a, **k: ImageValidation(False, "Exact words.", "Wrong words.", "mismatch"))
    rows = [row(1, "2026-01-01T00:00:00")]
    first = latest_run(cfg, rows, generate=True, client=provider)
    Path(first["results"][0]["image_path"]).unlink()
    second = latest_run(cfg, rows, generate=True, client=provider)
    assert second["results"][0]["status"] == "cached_artifact_missing"
    assert provider.calls == 1
    assert not second["complete"]


def test_recheck_validates_saved_image_without_provider_call(tmp_path, monkeypatch):
    import hashlib
    from highlight_art.recheck import recheck_run
    cfg = config(tmp_path, monkeypatch)
    provider = FakeProvider()
    monkeypatch.setattr("highlight_art.images.check_ocr", lambda _: None)
    monkeypatch.setattr("highlight_art.recheck.check_ocr", lambda _: None)
    monkeypatch.setattr("highlight_art.workflow.validate_exact_quote", lambda *a, **k: ImageValidation(False, "Exact words.", "Wrong words.", "mismatch"))
    first = latest_run(cfg, [row(1, "2026-01-01T00:00:00")], generate=True, client=provider)
    monkeypatch.setattr("highlight_art.recheck.validate_exact_quote", lambda image, *a, **k: ImageValidation(True, "Exact words.", "Exact words.", "ok", hashlib.sha256(image).hexdigest()))
    result = recheck_run(cfg, first["run_id"])
    assert result["complete"]
    assert result["active_backgrounds"] == 1
    assert provider.calls == 1
    assert Store(cfg.paths.state_root).read_json(Path(first["report_path"]))["results"][0]["status"] == "needs_review"
    with pytest.raises(ValueError):
        recheck_run(cfg, "../../outside")
