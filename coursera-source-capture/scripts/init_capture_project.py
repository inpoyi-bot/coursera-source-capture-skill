#!/usr/bin/env python3
"""Pin a new or verified existing directory as the active capture project root."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from capture_paths import MARKER_NAME, PROJECT_TYPE, marker_payload, reject_archive


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("project_root", type=Path)
    parser.add_argument(
        "--adopt-existing",
        action="store_true",
        help="adopt an existing directory only when its capture contract is present",
    )
    args = parser.parse_args()

    root = args.project_root.expanduser().resolve()
    marker = root / MARKER_NAME
    if marker.is_file():
        marker_payload(root)
        reject_archive(root)
        print(f"project_root={root}")
        print("marker_status=existing_active")
        return

    if root.exists() and any(root.iterdir()):
        if not args.adopt_existing:
            raise RuntimeError(
                f"Refusing non-empty unpinned directory {root}; use --adopt-existing "
                "only after verifying it is the authoritative capture project"
            )
        reject_archive(root)
        required = [root / "capture_policy.md", root / "raw", root / "readable"]
        missing = [path.name for path in required if not path.exists()]
        if missing:
            raise RuntimeError(
                f"Existing directory lacks capture contract entries: {', '.join(missing)}"
            )
    else:
        root.mkdir(parents=True, exist_ok=True)

    (root / "raw").mkdir(exist_ok=True)
    (root / "readable").mkdir(exist_ok=True)
    payload = {
        "schema_version": 1,
        "project_type": PROJECT_TYPE,
        "status": "active",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "purpose": "authoritative Coursera source-capture output root",
    }
    marker.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"project_root={root}")
    print("marker_status=created_active")


if __name__ == "__main__":
    main()
