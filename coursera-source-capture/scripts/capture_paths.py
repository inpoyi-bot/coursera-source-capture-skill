#!/usr/bin/env python3
"""Resolve and enforce the active Coursera capture project root."""

from __future__ import annotations

import json
from pathlib import Path


MARKER_NAME = ".coursera-source-capture-root.json"
PROJECT_TYPE = "coursera-source-capture"
ARCHIVE_PHRASES = (
    "merged archive",
    "do not continue capture",
    "retained only as",
)


def marker_payload(root: Path) -> dict[str, object]:
    marker = root / MARKER_NAME
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Invalid capture-root marker: {marker}: {error}") from error
    if not isinstance(data, dict):
        raise RuntimeError(f"Capture-root marker must be a JSON object: {marker}")
    if data.get("schema_version") != 1:
        raise RuntimeError(f"Unsupported capture-root marker schema: {marker}")
    if data.get("project_type") != PROJECT_TYPE:
        raise RuntimeError(f"Wrong project_type in capture-root marker: {marker}")
    if data.get("status") != "active":
        raise RuntimeError(f"Capture root is not active: {marker}")
    return data


def reject_archive(root: Path) -> None:
    readme = root / "README.md"
    if not readme.is_file():
        return
    text = readme.read_text(encoding="utf-8", errors="replace").casefold()
    matched = [phrase for phrase in ARCHIVE_PHRASES if phrase in text]
    if matched:
        raise RuntimeError(
            f"Refusing archive/mirror capture root {root}: README contains {matched[0]!r}"
        )


def require_project_root(target: Path) -> Path:
    """Return the active marker parent that contains target, or fail closed."""
    resolved = target.expanduser().resolve()
    start = resolved if resolved.is_dir() else resolved.parent
    for candidate in (start, *start.parents):
        marker = candidate / MARKER_NAME
        if not marker.is_file():
            continue
        marker_payload(candidate)
        reject_archive(candidate)
        try:
            resolved.relative_to(candidate)
        except ValueError as error:
            raise RuntimeError(f"Output escapes capture root: {resolved}") from error
        return candidate
    raise RuntimeError(
        f"No active {MARKER_NAME} found above {resolved}. "
        "Pin or adopt the authoritative project root before capture."
    )
