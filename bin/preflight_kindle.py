#!/usr/bin/env python3
"""Read-only mounted-Kindle preflight."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path


def find_mount(explicit: str | None) -> Path:
    candidates = [Path(explicit)] if explicit else sorted(Path("/Volumes").glob("*"))
    matches = [path for path in candidates if (path / "koreader" / "plugins").is_dir()]
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one mounted Kindle with koreader/plugins; found {len(matches)}")
    return matches[0]


def inspect(mount: Path) -> dict:
    version = mount / "system" / "version.txt"
    usage = shutil.disk_usage(mount)
    return {
        "mount": str(mount),
        "firmware": version.read_text().strip() if version.exists() else None,
        "koreader_plugins": (mount / "koreader" / "plugins").is_dir(),
        "kual": (mount / "documents" / "KUAL.sh").exists() or (mount / "documents" / "KUAL.jar").exists(),
        "mrinstaller": (mount / "extensions" / "MRInstaller").is_dir(),
        "linkss": (mount / "linkss" / "screensavers").is_dir(),
        "free_bytes": usage.free,
        "expected_resolution": [1264, 1680],
        "special_offers": "must be verified on the live device; not derivable from USB backup",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mount")
    args = parser.parse_args()
    try:
        report = inspect(find_mount(args.mount))
    except (OSError, RuntimeError) as exc:
        sys.exit(str(exc))
    print(json.dumps(report, indent=2, sort_keys=True))
    expected = "5.16.2.1.1"
    if not report["firmware"] or expected not in report["firmware"]:
        sys.exit(f"unexpected or missing firmware; expected {expected}")


if __name__ == "__main__":
    main()
