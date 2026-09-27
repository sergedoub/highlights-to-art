import hashlib

from datetime import UTC, datetime, timedelta

from highlight_art.models import Background
from highlight_art.rotation import build_manifest
from highlight_art.store import Store


def add_background(store, index, *, first="", last="", count=0):
    background = Background(
        id=f"{'a' * 23}{index % 10}-{index:012x}",
        highlight_id=f"{index:024x}",
        prompt_revision="revision",
        model="model",
        attempt=1,
        image_sha256=hashlib.sha256(b"png").hexdigest(),
        width=1264,
        height=1680,
        ocr_text=f"quote {index}",
        created_at=(datetime.now(UTC) - timedelta(days=index)).isoformat(),
        first_published_at=first,
        last_published_at=last,
        publish_count=count,
    )
    store.save_background(background, b"png")
    return background


def test_manifest_is_bounded_and_includes_new_unpublished_art(tmp_path):
    store = Store(tmp_path)
    old = (datetime.now(UTC) - timedelta(days=30)).isoformat()
    for index in range(10):
        add_background(store, index, first="" if index < 2 else old, last=old, count=index)
    manifest = build_manifest(store, active_size=5, new_image_days=7)
    assert len(manifest["backgrounds"]) == 5
    selected = {row["highlight_id"] for row in manifest["backgrounds"]}
    assert f"{0:024x}" in selected
    assert f"{1:024x}" in selected


def test_manifest_updates_publication_history(tmp_path):
    store = Store(tmp_path)
    background = add_background(store, 1)
    build_manifest(store, active_size=1)
    updated = next(store.iter_backgrounds())
    assert updated.first_published_at
    assert updated.last_published_at
    assert updated.publish_count == 1



def test_manifest_excludes_missing_or_modified_images(tmp_path):
    store = Store(tmp_path)
    missing = add_background(store, 1)
    modified = add_background(store, 2)
    store.background_path(missing.id).unlink()
    store.background_path(modified.id).write_bytes(b"changed")
    assert build_manifest(store)["backgrounds"] == []
