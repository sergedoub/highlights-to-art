#!/usr/bin/env python3
"""Render launchd templates; installation requires an explicit flag."""
from __future__ import annotations

import argparse
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = sorted((ROOT / "launchd").glob("*.plist.template"))


def render(template: Path) -> str:
    return template.read_text().replace("__PROJECT_ROOT__", str(ROOT))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--install", action="store_true", help="write to ~/Library/LaunchAgents")
    args = parser.parse_args()
    if not args.install:
        for template in TEMPLATES:
            print(f"--- {template.name.removesuffix('.template')} ---")
            print(render(template))
        return
    target = Path.home() / "Library" / "LaunchAgents"
    target.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    for template in TEMPLATES:
        destination = target / template.name.removesuffix(".template")
        if destination.exists():
            shutil.copy2(destination, destination.with_suffix(f".plist.bak-{timestamp}"))
        destination.write_text(render(template))
        print(destination)


if __name__ == "__main__":
    main()
