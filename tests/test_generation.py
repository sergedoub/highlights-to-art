from pathlib import Path

from highlight_art.generation import build_prompt, eligible_highlights, experiment_candidates
from highlight_art.ingest import highlight_id
from highlight_art.models import Highlight
from highlight_art.store import Store


def make_highlight(text):
    return Highlight(
        id=highlight_id("test", "Work", "1", text), source="test", work_title="Work",
        author="Author", location="1", highlighted_at="", text=text,
    )


def test_prompt_contains_full_quote_without_format_interpolation():
    highlight = make_highlight("Use {braces} and every word.")
    prompt = build_prompt("SYSTEM", "{{work_title}} {{author}} <{{quote}}>", highlight)
    assert "<Use {braces} and every word.>" in prompt


def test_eligibility_is_shortest_first_and_never_truncates(tmp_path):
    store = Store(tmp_path)
    short = make_highlight("short")
    medium = make_highlight("medium length")
    long = make_highlight("x" * 30)
    for row in (long, medium, short):
        store.add_highlight(row)
    rows = eligible_highlights(store, 20)
    assert [row.text for row in rows] == ["short", "medium length"]
    assert all(row.text != long.text[:20] for row in rows)


def test_experiment_sampling_is_stratified(tmp_path):
    store = Store(tmp_path)
    for length in range(10, 101, 10):
        store.add_highlight(make_highlight("x" * length))
    buckets = experiment_candidates(store, (50, 100), 3)
    assert len(buckets[50]) == 3
    assert len(buckets[100]) == 3
    assert all(len(row.text) <= 50 for row in buckets[50])
    assert all(50 < len(row.text) <= 100 for row in buckets[100])
