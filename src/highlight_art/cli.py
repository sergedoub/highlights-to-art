"""Command-line interface."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from dataclasses import asdict
from pathlib import Path

from .config import load_config
from .generation import effective_character_limit, eligible_highlights, run_length_experiment
from .ingest import ingest_bowerbird_events, ingest_clippings, parse_clippings
from .workflow import latest_run
from .recheck import recheck_run
from .images import check_ocr
from .pipeline import run_pipeline
from .relay import serve
from .rotation import build_manifest, current_manifest
from .store import Store


def _print(payload) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))


def _config(args, *, xai: bool = False, relay: bool = False):
    try:
        return load_config(args.config, require_provider=xai, require_relay=relay)
    except (OSError, ValueError) as exc:
        sys.exit(str(exc))


def command_import_clippings(args) -> None:
    config = _config(args)
    payload = Path(args.path).read_bytes()
    _print(ingest_clippings(Store(config.paths.state_root), payload))


def command_import_bowerbird(args) -> None:
    config = _config(args)
    directory = Path(args.path) if args.path else config.paths.bowerbird_events
    if not directory:
        sys.exit("no Bowerbird events directory configured")
    _print(ingest_bowerbird_events(Store(config.paths.state_root), directory))


def command_dry_run(args) -> None:
    config = _config(args)
    store = Store(config.paths.state_root)
    limit = effective_character_limit(config, store)
    _print({
        "highlights": len(list(store.iter_highlights())),
        "backgrounds": len(list(store.iter_backgrounds())),
        "character_limit": limit,
        "eligible": len(eligible_highlights(store, limit)),
        "active_manifest": len(current_manifest(store).get("backgrounds", [])),
    })


def command_experiment(args) -> None:
    config = _config(args, xai=True)
    _print(run_length_experiment(config, Store(config.paths.state_root)))


def command_run(args) -> None:
    config = _config(args, xai=True)
    report = run_pipeline(config, target=args.target)
    _print(report)
    if not report["complete"]:
        raise SystemExit(2)


def command_latest(args) -> None:
    config = _config(args, xai=args.generate)
    store = Store(config.paths.state_root)
    if args.clippings:
        payload = Path(args.clippings).expanduser().read_bytes()
        ingest_clippings(store, payload)
        rows = parse_clippings(payload)
    else:
        rows = [row for row in store.iter_highlights() if row.source == "kindle-clippings"]
    report = latest_run(config, rows, count=args.count, generate=args.generate, retry=args.retry)
    _print(report)
    if args.generate and not report["complete"]:
        raise SystemExit(2)


def command_recheck(args) -> None:
    report = recheck_run(_config(args), args.run_id)
    _print(report)
    if not report["complete"]:
        raise SystemExit(2)


def command_publish(args) -> None:
    config = _config(args)
    manifest = build_manifest(
        Store(config.paths.state_root),
        active_size=config.rotation.active_size,
        new_image_days=config.rotation.new_image_days,
    )
    _print({"active": len(manifest["backgrounds"]), "generated_at": manifest["generated_at"]})


def command_serve(args) -> None:
    config = _config(args, relay=True)
    serve(
        Store(config.paths.state_root), config.relay_token,
        config.relay.host, config.relay.port,
        max_body_bytes=config.relay.max_body_bytes,
    )


def command_doctor(args) -> None:
    config = _config(args)
    store = Store(config.paths.state_root)
    checks = {
        "config": True,
        "system_prompt": config.paths.system_prompt.exists(),
        "image_prompt": config.paths.image_prompt.exists(),
        "tesseract": bool(shutil.which("tesseract")),
        "provider": config.generation.provider,
        "provider_api_key": bool(config.api_key),
        "ocr_languages": config.generation.ocr_languages,
        "relay_token": len(config.relay_token) >= 24,
        "bowerbird_events": bool(config.paths.bowerbird_events and config.paths.bowerbird_events.is_dir()),
        "character_limit": effective_character_limit(config, store),
    }
    try:
        check_ocr(config.generation.ocr_languages)
        checks["ocr_ready"] = True
    except (OSError, RuntimeError):
        checks["ocr_ready"] = False
    _print(checks)
    if not all((checks["system_prompt"], checks["image_prompt"], checks["ocr_ready"], checks["provider_api_key"])):
        raise SystemExit(1)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="highlight-art")
    parser.add_argument("--config", default="config.toml")
    sub = parser.add_subparsers(dest="command", required=True)
    commands = {
        "latest": command_latest,
        "recheck": command_recheck,
        "import-clippings": command_import_clippings,
        "import-bowerbird": command_import_bowerbird,
        "dry-run": command_dry_run,
        "experiment": command_experiment,
        "run": command_run,
        "publish": command_publish,
        "serve": command_serve,
        "doctor": command_doctor,
    }
    for name, callback in commands.items():
        child = sub.add_parser(name)
        child.set_defaults(callback=callback)
        if name == "latest":
            child.add_argument("--clippings", help="path to My Clippings.txt on a mounted Kindle or backup")
            child.add_argument("--count", type=int, default=5)
            child.add_argument("--generate", action="store_true", help="make paid image requests (otherwise select only)")
            child.add_argument("--retry", action="store_true", help="explicitly regenerate previously attempted images")
        elif name == "recheck":
            child.add_argument("run_id")
        elif name == "import-clippings":
            child.add_argument("path")
        elif name == "import-bowerbird":
            child.add_argument("path", nargs="?")
        elif name == "run":
            child.add_argument("--target", type=int)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        args.callback(args)
    except (OSError, RuntimeError, ValueError) as exc:
        sys.exit(str(exc))


if __name__ == "__main__":
    main()
