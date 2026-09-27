"""Repeatable newest-highlight workflow. Paid requests are bounded and resumable."""
from __future__ import annotations

import hashlib
import json
import uuid
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path

from .generation import build_prompt, prompt_revision
from .images import inspect_kindle_png, to_kindle_png, validate_exact_quote
from .models import Background
from .providers import create_provider
from .rotation import build_manifest
from .selection import newest_highlights
from .store import Store, utc_now


@contextmanager
def generation_lock(store):
    import fcntl
    with (store.state / "generation.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Another generation run is active for this state directory") from None
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def latest_run(config, rows, *, count=5, generate=False, retry=False, client=None):
    selected = newest_highlights(rows, count)
    store = Store(config.paths.state_root)
    report = {"created_at": utc_now(), "provider": config.generation.provider,
              "model": config.generation.model, "api_calls": 0,
              "selected": [row.to_dict() for row in selected], "results": []}
    if not generate:
        return report
    if not selected:
        raise ValueError("No non-empty highlights found")
    # Check OCR before spending; validation must never silently become optional.
    from .images import check_ocr
    check_ocr(config.generation.ocr_languages)
    generation = config.generation
    system = config.paths.system_prompt.read_text()
    template = config.paths.image_prompt.read_text()
    provider = client or create_provider(config)
    run_id = uuid.uuid4().hex[:16]
    run_path = store.root / "runs" / run_id
    run_path.mkdir(parents=True)
    report["run_id"] = run_id
    report["report_path"] = str(run_path / "report.json")
    with generation_lock(store):
        for row in selected:
            prompt = build_prompt(system, template, row)
            identity = json.dumps([row.id, generation.provider, generation.model, generation.api_base,
                                   generation.size, generation.quality, generation.width, generation.height,
                                   generation.ocr_languages, prompt], ensure_ascii=False)
            fingerprint = hashlib.sha256(identity.encode()).hexdigest()[:24]
            cached_path = store.root / "candidates" / f"{fingerprint}.json"
            cached = store.read_json(cached_path)
            # An unknown outcome may still have been billed; only explicit retry repeats it.
            if cached and not retry:
                reused = dict(cached, cached=True)
                if cached.get("image_path"):
                    image_path = Path(cached["image_path"])
                    if not image_path.is_file():
                        reused["status"] = "cached_artifact_missing"
                    elif cached["status"] == "validated":
                        expected = cached["validation"]["image_sha256"]
                        published = store.background_path(cached["background_id"])
                        if (hashlib.sha256(image_path.read_bytes()).hexdigest() != expected
                                or not published.is_file()
                                or hashlib.sha256(published.read_bytes()).hexdigest() != expected):
                            reused["status"] = "cached_artifact_invalid"
                report["results"].append(reused)
                continue
            result = {"highlight_id": row.id, "status": "pending", "fingerprint": fingerprint}
            if report["api_calls"] >= generation.max_api_calls_per_run:
                result["status"] = "budget_exhausted"
                report["results"].append(result)
                continue
            if generation.character_limit > 0 and len(row.text) > generation.character_limit:
                result["status"] = "over_character_limit"
                report["results"].append(result)
                continue
            attempt_dir = run_path / row.id
            attempt_dir.mkdir()
            store.atomic_write(attempt_dir / "prompt.txt", prompt.encode())
            result.update(status="request_started", created_at=utc_now(), run_id=run_id)
            store.write_json(cached_path, result)
            report["api_calls"] += 1
            try:
                image = provider.generate(prompt, generation.model)
                store.atomic_write(attempt_dir / "source.png", image.payload)
                converted = to_kindle_png(image.payload, generation.width, generation.height)
                output = attempt_dir / "kindle.png"
                store.atomic_write(output, converted)
                result["image_path"] = str(output)
                validation = validate_exact_quote(converted, row.text, generation.width, generation.height,
                                                  languages=generation.ocr_languages)
                result["validation"] = asdict(validation)
                result["status"] = "validated" if validation.ok else "needs_review"
                if validation.ok:
                    background_id = f"{row.id}-{validation.image_sha256[:12]}"
                    store.save_background(Background(
                        id=background_id, highlight_id=row.id, prompt_revision=prompt_revision(system, template),
                        model=generation.model, attempt=1, image_sha256=validation.image_sha256,
                        width=generation.width, height=generation.height, ocr_text=validation.observed,
                        created_at=utc_now(), extra={"provider": generation.provider, "run_id": run_id},
                    ), converted)
                    result["background_id"] = background_id
            except (OSError, RuntimeError, ValueError) as exc:
                # Do not leak provider error bodies or prompts into command output.
                result["status"] = "failed"
                result["error_type"] = type(exc).__name__
                result["http_status"] = getattr(exc, "status", None)
                result["error"] = "Generation or validation failed; check provider access, billing, network and OCR. No automatic retry."
            store.write_json(cached_path, result)
            store.write_json(attempt_dir / "result.json", result)
            report["results"].append(result)
            store.write_json(run_path / "report.json", report)
        report["complete"] = all(r["status"] == "validated" for r in report["results"])
        report["generated_images"] = sum(bool(r.get("image_path")) for r in report["results"])
        report["validated_images"] = sum(r["status"] == "validated" for r in report["results"])
        manifest = build_manifest(store, active_size=config.rotation.active_size, new_image_days=config.rotation.new_image_days)
        report["active_backgrounds"] = len(manifest["backgrounds"])
        store.write_json(run_path / "report.json", report)
        store.write_json(store.state / "latest-run.json", report)
    return report
