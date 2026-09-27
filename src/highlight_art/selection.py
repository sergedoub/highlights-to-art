"""Chronological selection without depending on the machine's locale."""
from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Iterable

from .models import Highlight

_MONTHS = {name: i for i, name in enumerate(
    "January February March April May June July August September October November December".split(), 1)}


def highlight_date(value: str) -> datetime:
    try:
        date = datetime.fromisoformat(value.replace("Z", "+00:00"))
        # Kindle clippings have no timezone. Compare their recorded wall-clock times.
        return date.astimezone(UTC).replace(tzinfo=None) if date.tzinfo else date
    except ValueError:
        pass
    match = re.fullmatch(r"\w+, (\w+) (\d{1,2}), (\d{4}) (\d{1,2}):(\d{2}):(\d{2}) (AM|PM)", value)
    if not match:
        raise ValueError("Unsupported highlight date; expected English Kindle metadata or ISO 8601")
    month, day, year, hour, minute, second, period = match.groups()
    if month not in _MONTHS or not 1 <= int(hour) <= 12:
        raise ValueError("Invalid Kindle highlight date")
    return datetime(int(year), _MONTHS[month], int(day), int(hour) % 12 + (12 if period == "PM" else 0), int(minute), int(second))


def newest_highlights(rows: Iterable[Highlight], count: int = 5) -> list[Highlight]:
    if not 1 <= count <= 100:
        raise ValueError("count must be between 1 and 100")
    unique: dict[str, tuple[datetime, Highlight]] = {}
    for row in rows:
        if not row.text.strip():
            continue
        date = highlight_date(row.highlighted_at)
        if row.id not in unique or date > unique[row.id][0]:
            unique[row.id] = (date, row)
    return [row for _, row in sorted(unique.values(), key=lambda item: (item[0], item[1].id), reverse=True)[:count]]
