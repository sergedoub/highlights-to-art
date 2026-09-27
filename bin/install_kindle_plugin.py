#!/usr/bin/env python3
"""Install the Highlight Art KOReader plugin on a mounted Kindle."""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def lua_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def find_mount(explicit: str | None) -> Path:
    candidates = [Path(explicit)] if explicit else sorted(Path("/Volumes").glob("*"))
    matches = [path for path in candidates if (path / "koreader" / "plugins").is_dir()]
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one mounted Kindle with koreader/plugins; found {len(matches)}")
    return matches[0]


def install(mount: Path, relay_url: str, token: str, *, enable_stock: bool = False) -> tuple[Path, Path]:
    if not relay_url.startswith(("http://", "https://")):
        raise ValueError("relay URL must start with http:// or https://")
    if len(token) < 24:
        raise ValueError("HIGHLIGHT_ART_RELAY_TOKEN must contain at least 24 characters")
    if enable_stock and not (mount / "linkss" / "screensavers").is_dir():
        raise ValueError("--enable-stock requires an already smoke-tested linkss/screensavers directory")
    plugin = mount / "koreader" / "plugins" / "highlightart.koplugin"
    shutil.copytree(ROOT / "kindle" / "highlightart.koplugin", plugin, dirs_exist_ok=True)
    (mount / "highlight-art" / "screensavers").mkdir(parents=True, exist_ok=True)
    settings = mount / "koreader" / "settings" / "highlightart.lua"
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text(
        "return {\n"
        "    [\"relay\"] = {\n"
        f"        [\"url\"] = {lua_string(relay_url.rstrip('/'))},\n"
        f"        [\"token\"] = {lua_string(token)},\n"
        "        [\"poll_seconds\"] = 300,\n"
        "        [\"manage_screensaver\"] = true,\n"
        f"        [\"linkss_enabled\"] = {'true' if enable_stock else 'false'},\n"
        "    },\n"
        "    [\"outbox\"] = {},\n"
        "    [\"downloads\"] = {},\n"
        "}\n"
    )
    return plugin, settings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mount")
    parser.add_argument("--relay-url", required=True)
    parser.add_argument("--enable-stock", action="store_true")
    args = parser.parse_args()
    try:
        plugin, settings = install(
            find_mount(args.mount), args.relay_url,
            os.getenv("HIGHLIGHT_ART_RELAY_TOKEN", ""),
            enable_stock=args.enable_stock,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        sys.exit(str(exc))
    print(f"installed plugin: {plugin}")
    print(f"wrote settings: {settings}")
    print("Safely eject the Kindle, then restart KOReader.")


if __name__ == "__main__":
    main()
