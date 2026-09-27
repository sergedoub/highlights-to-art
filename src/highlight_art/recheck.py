"""Revalidate saved output without contacting an image provider."""
from __future__ import annotations

import hashlib
import re
from dataclasses import asdict
from pathlib import Path

from .images import check_ocr, validate_exact_quote
from .models import Background
from .rotation import build_manifest
from .store import Store, utc_now
from .workflow import generation_lock


def recheck_run(config, run_id: str):
    if not re.fullmatch(r"[a-f0-9]{16}", run_id):
        raise ValueError("Invalid run ID")
    store = Store(config.paths.state_root)
    root = store.root / "runs" / run_id
    report = store.read_json(root / "report.json")
    if not report:
        raise ValueError("Run report not found")
    check_ocr(config.generation.ocr_languages)
    selected = {row["id"]: row for row in report["selected"]}
    with generation_lock(store):
        for result in report["results"]:
            if not result.get("image_path"):
                continue
            path = Path(result["image_path"])
            if not path.is_file():
                result["status"] = "cached_artifact_missing"
                continue
            row = selected[result["highlight_id"]]
            payload = path.read_bytes()
            validation = validate_exact_quote(payload, row["text"], config.generation.width,
                                               config.generation.height, languages=config.generation.ocr_languages)
            result["validation"] = asdict(validation)
            result["status"] = "validated" if validation.ok else "needs_review"
            result["rechecked_at"] = utc_now()
            if validation.ok:
                background_id = f"{row['id']}-{validation.image_sha256[:12]}"
                prompt = path.parent / "prompt.txt"
                revision = hashlib.sha256(prompt.read_bytes()).hexdigest()[:12] if prompt.is_file() else "unknown"
                store.save_background(Background(
                    id=background_id, highlight_id=row["id"], prompt_revision=revision, model=report["model"],
                    attempt=1, image_sha256=validation.image_sha256, width=config.generation.width,
                    height=config.generation.height, ocr_text=validation.observed, created_at=utc_now(),
                    extra={"provider": report["provider"], "run_id": run_id, "rechecked": True},
                ), payload)
                result["background_id"] = background_id
            store.write_json(store.root / "candidates" / f"{result['fingerprint']}.json", result)
        report["rechecked_at"] = utc_now()
        report["complete"] = all(r["status"] == "validated" for r in report["results"])
        report["validated_images"] = sum(r["status"] == "validated" for r in report["results"])
        report["active_backgrounds"] = len(build_manifest(store, active_size=config.rotation.active_size,
                                                         new_image_days=config.rotation.new_image_days)["backgrounds"])
        report["report_path"] = str(root / "recheck-report.json")
        store.write_json(root / "recheck-report.json", report)
        store.write_json(store.state / "latest-run.json", report)
    return report
