from highlight_art.ingest import ingest_bowerbird_events, ingest_clippings, parse_clippings
from highlight_art.store import Store


CLIPPINGS = """\ufeffShort Work (Ada Author)\r
- Your Highlight on page 1 | Location 10-11 | Added on Monday, January 1, 2024 1:00:00 PM\r
\r
Every word survives.\r
==========\r
Empty Work (No Text)\r
- Your Highlight on Location 2 | Added on Tuesday, January 2, 2024 2:00:00 PM\r
\r
\r
==========\r
Short Work (Ada Author)\r
- Your Note on page 1 | Added on Monday, January 1, 2024 1:01:00 PM\r
\r
Not a highlight.\r
==========\r
"""


def test_parse_clippings_handles_bom_crlf_and_empty_highlights():
    rows = parse_clippings(CLIPPINGS.encode())
    assert len(rows) == 2
    assert rows[0].work_title == "Short Work"
    assert rows[0].author == "Ada Author"
    assert rows[0].location == "page 1 | Location 10-11"
    assert rows[0].text == "Every word survives."
    assert rows[1].text == ""


def test_ingest_clippings_is_idempotent_and_ignores_empty(tmp_path):
    store = Store(tmp_path)
    first = ingest_clippings(store, CLIPPINGS)
    second = ingest_clippings(store, CLIPPINGS)
    assert first["seen"] == 2
    assert first["added"] == 1
    assert second["added"] == 0
    assert len(list(store.iter_highlights())) == 1


def test_ingest_bowerbird_deduplicates_repeated_annotation_events(tmp_path):
    store = Store(tmp_path / "state")
    events = tmp_path / "events"
    events.mkdir()
    body = '{"article_id":"123","annotations":[{"text":"Same quote","page":4,"datetime":"today"}]}'
    (events / "one.json").write_text(body)
    (events / "two.json").write_text(body)
    result = ingest_bowerbird_events(store, events)
    assert result == {"seen": 2, "added": 1}
