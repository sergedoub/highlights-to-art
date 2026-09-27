"""Atomic, inspectable file-backed storage."""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from .models import Background, Highlight


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class Store:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.highlights = self.root / "highlights"
        self.backgrounds = self.root / "backgrounds"
        self.attempts = self.root / "attempts"
        self.quarantine = self.root / "quarantine"
        self.clippings = self.root / "clippings"
        self.receipts = self.root / "receipts"
        self.state = self.root / "state"
        for directory in (
            self.highlights, self.backgrounds, self.attempts, self.quarantine,
            self.clippings, self.receipts, self.state,
        ):
            directory.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def atomic_write(path: Path, payload: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)

    @classmethod
    def write_json(cls, path: Path, payload: Any) -> None:
        cls.atomic_write(path, (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode())

    @staticmethod
    def read_json(path: Path, default: Any = None) -> Any:
        if not path.exists():
            return default
        return json.loads(path.read_text())

    def add_highlight(self, highlight: Highlight) -> bool:
        path = self.highlights / f"{highlight.id}.json"
        if path.exists():
            from .selection import highlight_date
            previous = self.read_json(path)
            try:
                newer = highlight_date(highlight.highlighted_at) > highlight_date(previous["highlighted_at"])
            except ValueError:
                newer = False
            if newer:
                self.write_json(path, highlight.to_dict())
            return False
        self.write_json(path, highlight.to_dict())
        return True

    def iter_highlights(self) -> Iterable[Highlight]:
        for path in sorted(self.highlights.glob("*.json")):
            yield Highlight(**self.read_json(path))

    def get_highlight(self, highlight_id: str) -> Highlight:
        return Highlight(**self.read_json(self.highlights / f"{highlight_id}.json"))

    def background_path(self, background_id: str) -> Path:
        return self.backgrounds / f"{background_id}.png"

    def background_meta_path(self, background_id: str) -> Path:
        return self.backgrounds / f"{background_id}.json"

    def has_background_for(self, highlight_id: str) -> bool:
        return any(self.backgrounds.glob(f"{highlight_id}-*.json"))

    def save_background(self, background: Background, image: bytes) -> None:
        self.atomic_write(self.background_path(background.id), image)
        self.write_json(self.background_meta_path(background.id), background.to_dict())

    def iter_backgrounds(self) -> Iterable[Background]:
        for path in sorted(self.backgrounds.glob("*.json")):
            yield Background(**self.read_json(path))

    def save_attempt(self, highlight_id: str, attempt: int, payload: dict[str, Any]) -> None:
        self.write_json(self.attempts / highlight_id / f"{attempt:02d}.json", payload)

    def attempt_count(self, highlight_id: str) -> int:
        return len(list((self.attempts / highlight_id).glob("*.json")))

    def quarantine_attempt(self, highlight_id: str, attempt: int, payload: dict[str, Any]) -> None:
        self.write_json(self.quarantine / f"{highlight_id}-{attempt:02d}.json", payload)

    def save_clippings_snapshot(self, payload: bytes) -> tuple[str, bool]:
        digest = hashlib.sha256(payload).hexdigest()
        path = self.clippings / f"{digest}.txt"
        created = not path.exists()
        if created:
            self.atomic_write(path, payload)
        return digest, created

    def save_receipt(self, payload: dict[str, Any]) -> str:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        receipt_id = str(payload.get("receipt_id") or hashlib.sha256(canonical).hexdigest()[:24])
        if not re.fullmatch(r"[A-Za-z0-9._-]{8,80}", receipt_id):
            raise ValueError("invalid receipt_id")
        self.write_json(self.receipts / f"{receipt_id}.json", dict(payload, receipt_id=receipt_id, received_at=utc_now()))
        return receipt_id
