"""Fair, bounded publication rotation."""
from __future__ import annotations

import hashlib

from datetime import UTC, datetime, timedelta
from pathlib import Path

from .models import Background
from .store import Store, utc_now


def _parse(value: str) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def build_manifest(store: Store, *, active_size: int = 96, new_image_days: int = 7) -> dict:
    now = datetime.now(UTC)
    cutoff = now - timedelta(days=new_image_days)
    backgrounds = []
    for row in store.iter_backgrounds():
        path = store.background_path(row.id)
        if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == row.image_sha256:
            backgrounds.append(row)
    fresh = [
        row for row in backgrounds
        if not row.first_published_at or (_parse(row.first_published_at) or now) >= cutoff
    ]
    fresh.sort(key=lambda row: (row.first_published_at != "", row.created_at), reverse=False)
    selected = fresh[:active_size]
    selected_ids = {row.id for row in selected}
    older = [row for row in backgrounds if row.id not in selected_ids]
    older.sort(key=lambda row: (row.last_published_at or "", row.publish_count, row.created_at))
    selected.extend(older[: max(0, active_size - len(selected))])
    timestamp = utc_now()
    rows = []
    for background in selected:
        background.first_published_at = background.first_published_at or timestamp
        background.last_published_at = timestamp
        background.publish_count += 1
        store.write_json(store.background_meta_path(background.id), background.to_dict())
        rows.append({
            "id": background.id,
            "highlight_id": background.highlight_id,
            "sha256": background.image_sha256,
            "download_path": f"/v1/backgrounds/{background.id}.png",
            "width": background.width,
            "height": background.height,
        })
    manifest = {"version": 1, "generated_at": timestamp, "backgrounds": rows}
    store.write_json(store.state / "manifest.json", manifest)
    return manifest


def current_manifest(store: Store) -> dict:
    return store.read_json(store.state / "manifest.json", {"version": 1, "backgrounds": []})
