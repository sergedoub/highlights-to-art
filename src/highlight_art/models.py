"""Serializable domain records."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Highlight:
    id: str
    source: str
    work_title: str
    author: str
    location: str
    highlighted_at: str
    text: str
    note: str = ""
    source_id: str = ""
    ingested_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Background:
    id: str
    highlight_id: str
    prompt_revision: str
    model: str
    attempt: int
    image_sha256: str
    width: int
    height: int
    ocr_text: str
    created_at: str
    first_published_at: str = ""
    last_published_at: str = ""
    publish_count: int = 0
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
