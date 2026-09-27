"""Source adapters for Kindle clippings, KOReader, and Bowerbird."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

from .models import Highlight
from .store import Store, utc_now


_HIGHLIGHT_MARKER = re.compile(r"^-\s*Your Highlight\b", re.IGNORECASE)
_ADDED_ON = re.compile(r"\|\s*Added on\s+(.+?)\s*$", re.IGNORECASE)
_AUTHOR_SUFFIX = re.compile(r"^(.*?)\s+\(([^()]*)\)\s*$")


def _canonical_text(value: str) -> str:
    return " ".join(value.replace("\ufeff", "").split())


def highlight_id(source: str, work: str, location: str, text: str, source_id: str = "") -> str:
    identity = "\x1f".join((
        source_id or source,
        _canonical_text(work),
        _canonical_text(location),
        _canonical_text(text),
    ))
    return hashlib.sha256(identity.encode()).hexdigest()[:24]


def _split_work(value: str) -> tuple[str, str]:
    match = _AUTHOR_SUFFIX.match(value.strip())
    if not match:
        return value.strip(), ""
    return match.group(1).strip(), match.group(2).strip()


def parse_clippings(payload: str | bytes, *, source: str = "kindle-clippings") -> list[Highlight]:
    if isinstance(payload, bytes):
        text = payload.decode("utf-8-sig", errors="replace")
    else:
        text = payload.removeprefix("\ufeff")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    records: list[Highlight] = []
    for block in re.split(r"^==========\s*$", text, flags=re.MULTILINE):
        lines = block.strip("\n\ufeff ").splitlines()
        if len(lines) < 2 or not _HIGHLIGHT_MARKER.match(lines[1].strip()):
            continue
        work_title, author = _split_work(lines[0].strip().removeprefix("\ufeff"))
        metadata = lines[1].strip()
        added = _ADDED_ON.search(metadata)
        highlighted_at = added.group(1).strip() if added else ""
        location = _ADDED_ON.sub("", metadata).removeprefix("- Your Highlight on ").strip()
        body_start = 2
        while body_start < len(lines) and not lines[body_start].strip():
            body_start += 1
        quote = "\n".join(lines[body_start:]).strip()
        record_id = highlight_id(source, work_title, location, quote)
        records.append(Highlight(
            id=record_id,
            source=source,
            work_title=work_title,
            author=author,
            location=location,
            highlighted_at=highlighted_at,
            text=quote,
            ingested_at=utc_now(),
        ))
    return records


def ingest_clippings(store: Store, payload: str | bytes, *, source: str = "kindle-clippings") -> dict[str, int | str]:
    raw = payload.encode() if isinstance(payload, str) else payload
    digest, snapshot_created = store.save_clippings_snapshot(raw)
    records = parse_clippings(raw, source=source)
    added = sum(store.add_highlight(record) for record in records if record.text.strip())
    return {"snapshot": digest, "snapshot_created": int(snapshot_created), "seen": len(records), "added": added}


def parse_koreader_batch(payload: dict) -> list[Highlight]:
    rows = payload.get("highlights", [])
    if not isinstance(rows, list):
        raise ValueError("highlights must be a list")
    records: list[Highlight] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("each highlight must be an object")
        text = str(row.get("text", "")).strip()
        work = str(row.get("work_title", "Unknown work")).strip()
        location = str(row.get("location", "")).strip()
        source_id = str(row.get("source_id", "")).strip()
        record_id = highlight_id("koreader", work, location, text, source_id)
        records.append(Highlight(
            id=record_id,
            source="koreader",
            work_title=work,
            author=str(row.get("author", "")).strip(),
            location=location,
            highlighted_at=str(row.get("highlighted_at", "")).strip(),
            text=text,
            note=str(row.get("note", "")).strip(),
            source_id=source_id,
            ingested_at=utc_now(),
        ))
    return records


def ingest_koreader_batch(store: Store, payload: dict) -> dict[str, int]:
    records = parse_koreader_batch(payload)
    added = sum(store.add_highlight(record) for record in records if record.text)
    return {"seen": len(records), "added": added}


def ingest_bowerbird_events(store: Store, directory: str | Path) -> dict[str, int]:
    seen = added = 0
    for path in sorted(Path(directory).glob("*.json")):
        event = json.loads(path.read_text())
        article_id = str(event.get("article_id", ""))
        for annotation in event.get("annotations", []) or []:
            if not isinstance(annotation, dict):
                continue
            seen += 1
            text = str(annotation.get("text", "")).strip()
            location = str(annotation.get("page", ""))
            record = Highlight(
                id=highlight_id("bowerbird", article_id, location, text, article_id),
                source="bowerbird",
                source_id=article_id,
                work_title=f"Bowerbird article {article_id}",
                author="",
                location=location,
                highlighted_at=str(annotation.get("datetime", "")),
                text=text,
                note=str(annotation.get("note", "")).strip(),
                ingested_at=utc_now(),
            )
            if text:
                added += int(store.add_highlight(record))
    return {"seen": seen, "added": added}
