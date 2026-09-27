"""Prompt construction, curation, generation, and length experiments."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from .config import AppConfig
from .images import to_kindle_png, validate_exact_quote
from .models import Background, Highlight
from .store import Store, utc_now
from .providers import GeneratedImage, ImageProvider, create_provider


@dataclass(frozen=True)
class GenerationSummary:
    eligible: int
    attempted: int
    api_calls: int
    succeeded: int
    quarantined: int
    skipped_exhausted: int


def prompt_revision(system: str, image: str) -> str:
    return hashlib.sha256((system + "\x00" + image).encode()).hexdigest()[:12]


def build_prompt(system: str, image: str, highlight: Highlight, *, retry_feedback: str = "") -> str:
    fields = {"work_title": highlight.work_title or "Unknown work",
              "author": highlight.author or "Unknown author", "quote": highlight.text}
    body = re.sub(r"\{\{(work_title|author|quote)\}\}", lambda match: fields[match.group(1)], image)
    if retry_feedback:
        body += (
            "\n\nThe previous attempt failed exact-text validation. "
            "Correct the spelling, punctuation, ordering, and completeness. Validation feedback:\n"
            + retry_feedback
        )
    return system.rstrip() + "\n\n" + body.lstrip()


def eligible_highlights(store: Store, character_limit: int) -> list[Highlight]:
    if character_limit <= 0:
        return []
    rows = [
        row for row in store.iter_highlights()
        if row.text.strip() and len(row.text) <= character_limit and not store.has_background_for(row.id)
    ]
    return sorted(rows, key=lambda row: (len(row.text), row.highlighted_at, row.id))


def effective_character_limit(config: AppConfig, store: Store) -> int:
    configured = config.generation.character_limit
    if configured > 0:
        return configured
    experiment = store.read_json(store.state / "experiment.json", {})
    return int(experiment.get("selected_character_limit", 0))


def generate_batch(
    config: AppConfig,
    store: Store,
    *,
    client: ImageProvider | None = None,
    target: int | None = None,
) -> GenerationSummary:
    generation = config.generation
    character_limit = effective_character_limit(config, store)
    if character_limit <= 0:
        raise ValueError("character_limit is 0; run the length experiment and set a validated limit")
    system = config.paths.system_prompt.read_text()
    image_template = config.paths.image_prompt.read_text()
    revision = prompt_revision(system, image_template)
    image_client = client or create_provider(config)
    candidates = eligible_highlights(store, character_limit)
    wanted = target if target is not None else generation.publish_target
    api_calls = succeeded = quarantined = exhausted = attempted = 0
    for highlight in candidates:
        if succeeded >= wanted or api_calls >= generation.max_api_calls_per_run:
            break
        existing_attempts = store.attempt_count(highlight.id)
        if existing_attempts >= generation.max_attempts_per_highlight:
            exhausted += 1
            continue
        attempted += 1
        retry_feedback = ""
        for attempt in range(existing_attempts + 1, generation.max_attempts_per_highlight + 1):
            if api_calls >= generation.max_api_calls_per_run:
                break
            prompt = build_prompt(system, image_template, highlight, retry_feedback=retry_feedback)
            prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
            api_calls += 1
            generated = image_client.generate(prompt, generation.model)
            converted = to_kindle_png(generated.payload, generation.width, generation.height)
            result = validate_exact_quote(converted, highlight.text, generation.width, generation.height)
            attempt_record = {
                "attempt": attempt,
                "created_at": utc_now(),
                "highlight_id": highlight.id,
                "model": generation.model,
                "prompt_hash": prompt_hash,
                "prompt_revision": revision,
                "source_url": generated.source_url,
                "validation": {
                    "ok": result.ok,
                    "reason": result.reason,
                    "expected": result.expected,
                    "observed": result.observed,
                },
            }
            store.save_attempt(highlight.id, attempt, attempt_record)
            if result.ok:
                background_id = f"{highlight.id}-{result.image_sha256[:12]}"
                store.save_background(Background(
                    id=background_id,
                    highlight_id=highlight.id,
                    prompt_revision=revision,
                    model=generation.model,
                    attempt=attempt,
                    image_sha256=result.image_sha256,
                    width=generation.width,
                    height=generation.height,
                    ocr_text=result.observed,
                    created_at=utc_now(),
                ), converted)
                succeeded += 1
                break
            quarantined += 1
            store.quarantine_attempt(highlight.id, attempt, attempt_record)
            retry_feedback = f"Expected: {result.expected}\nOCR observed: {result.observed}\nReason: {result.reason}"
    return GenerationSummary(
        eligible=len(candidates), attempted=attempted, api_calls=api_calls,
        succeeded=succeeded, quarantined=quarantined, skipped_exhausted=exhausted,
    )


def experiment_candidates(store: Store, lengths: tuple[int, ...], samples_per_bucket: int) -> dict[int, list[Highlight]]:
    highlights = sorted((row for row in store.iter_highlights() if row.text.strip()), key=lambda row: len(row.text))
    buckets: dict[int, list[Highlight]] = {}
    lower = 0
    for upper in sorted(lengths):
        candidates = [row for row in highlights if lower < len(row.text) <= upper]
        if len(candidates) <= samples_per_bucket:
            buckets[upper] = candidates
        else:
            step = (len(candidates) - 1) / (samples_per_bucket - 1) if samples_per_bucket > 1 else 0
            buckets[upper] = [candidates[round(index * step)] for index in range(samples_per_bucket)]
        lower = upper
    return buckets


def run_length_experiment(
    config: AppConfig,
    store: Store,
    *,
    client: ImageProvider | None = None,
) -> dict:
    generation = config.generation
    system = config.paths.system_prompt.read_text()
    image_template = config.paths.image_prompt.read_text()
    revision = prompt_revision(system, image_template)
    image_client = client or create_provider(config)
    buckets = experiment_candidates(store, generation.experiment_lengths, generation.experiment_samples_per_bucket)
    api_calls = 0
    results: dict[str, dict] = {}
    complete = True
    for upper, candidates in buckets.items():
        passed = 0
        rows = []
        for highlight in candidates:
            success = store.has_background_for(highlight.id)
            attempts = store.attempt_count(highlight.id)
            retry_feedback = ""
            while not success and attempts < generation.max_attempts_per_highlight:
                if api_calls >= generation.experiment_max_api_calls:
                    complete = False
                    break
                attempts += 1
                prompt = build_prompt(system, image_template, highlight, retry_feedback=retry_feedback)
                generated = image_client.generate(prompt, generation.model)
                api_calls += 1
                converted = to_kindle_png(generated.payload, generation.width, generation.height)
                validation = validate_exact_quote(converted, highlight.text, generation.width, generation.height)
                attempt_record = {
                    "attempt": attempts,
                    "created_at": utc_now(),
                    "experiment_bucket": upper,
                    "highlight_id": highlight.id,
                    "model": generation.model,
                    "prompt_hash": hashlib.sha256(prompt.encode()).hexdigest(),
                    "prompt_revision": revision,
                    "source_url": generated.source_url,
                    "validation": {
                        "ok": validation.ok,
                        "reason": validation.reason,
                        "expected": validation.expected,
                        "observed": validation.observed,
                    },
                }
                store.save_attempt(highlight.id, attempts, attempt_record)
                if validation.ok:
                    background_id = f"{highlight.id}-{validation.image_sha256[:12]}"
                    store.save_background(Background(
                        id=background_id, highlight_id=highlight.id, prompt_revision=revision,
                        model=generation.model, attempt=attempts, image_sha256=validation.image_sha256,
                        width=generation.width, height=generation.height, ocr_text=validation.observed,
                        created_at=utc_now(), extra={"experiment_bucket": upper},
                    ), converted)
                    success = True
                else:
                    store.quarantine_attempt(highlight.id, attempts, attempt_record)
                    retry_feedback = (
                        f"Expected: {validation.expected}\nOCR observed: {validation.observed}\n"
                        f"Reason: {validation.reason}"
                    )
            if success:
                passed += 1
            rows.append({"highlight_id": highlight.id, "characters": len(highlight.text), "passed": success})
            if not complete:
                break
        total = len(rows)
        results[str(upper)] = {
            "passed": passed,
            "total": total,
            "pass_rate": passed / total if total else 0.0,
            "rows": rows,
        }
        if not complete:
            break
    selected = 0
    cumulative_passed = cumulative_total = 0
    if complete:
        for upper in sorted(buckets):
            bucket = results[str(upper)]
            cumulative_passed += bucket["passed"]
            cumulative_total += bucket["total"]
            if cumulative_total and cumulative_passed / cumulative_total >= generation.experiment_min_pass_rate:
                selected = upper
            else:
                break
    report = {
        "completed_at": utc_now(),
        "complete": complete,
        "api_calls": api_calls,
        "minimum_pass_rate": generation.experiment_min_pass_rate,
        "selected_character_limit": selected,
        "buckets": results,
    }
    store.write_json(store.state / "experiment.json", report)
    return report
