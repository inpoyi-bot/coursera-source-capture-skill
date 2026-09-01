#!/usr/bin/env python3
"""Synchronize unlocked/unknown Coursera widgets into a durable gap queue."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import date
from pathlib import Path

from capture_paths import require_project_root


QUEUE_SCHEMA_VERSION = 2
TRACKED_TYPES = {"ungradedWidget", "ungradedPlugin", "ungradedLti", "coach"}
OPEN_STATUSES = {
    "needs_inventory_refresh",
    "manual_capture_pending",
    "partial_capture",
    "captured_unverified",
    "blocked",
}
STATUS_DEFINITIONS = {
    "needs_inventory_refresh": "Item identity or current lock state is unknown; do not infer eligibility.",
    "manual_capture_pending": "Known unlocked item still requires capture.",
    "partial_capture": "Some metadata or provenance exists, but the body is missing or incomplete.",
    "captured_unverified": "Files exist but completeness, provenance, or hashes have not passed validation.",
    "verified": "Required sources and manifest evidence passed validation.",
    "blocked": "Capture was attempted but cannot currently proceed; retry condition is recorded.",
}


def new_queue() -> dict[str, object]:
    return {
        "schema_version": QUEUE_SCHEMA_VERSION,
        "last_updated": date.today().isoformat(),
        "policy": "capture_policy.md",
        "completion_rule": (
            "Do not declare full source-capture completion while an eligible or "
            "unknown item is needs_inventory_refresh, manual_capture_pending, "
            "partial_capture, captured_unverified, or blocked."
        ),
        "status_definitions": STATUS_DEFINITIONS,
        "counts": {},
        "course_counts": {},
        "items": [],
    }


def migrate_queue(data: dict[str, object]) -> bool:
    """Upgrade a schema-v1 single-course queue in memory without changing item state."""
    schema_version = data.get("schema_version")
    items = data.get("items")
    if not isinstance(items, list):
        raise ValueError("Queue items must be a list")

    migrated = False
    if schema_version == 1:
        legacy_course_slug = data.get("course_slug")
        for item in items:
            if not isinstance(item, dict):
                raise ValueError("Every queue item must be an object")
            course_slug = item.get("course_slug") or legacy_course_slug
            if not isinstance(course_slug, str) or not course_slug:
                raise ValueError(
                    "Schema-v1 queue cannot be migrated without a course_slug"
                )
            item["course_slug"] = course_slug
        data.pop("course_slug", None)
        data["schema_version"] = QUEUE_SCHEMA_VERSION
        migrated = True
    elif schema_version != QUEUE_SCHEMA_VERSION:
        raise ValueError(f"Unsupported queue schema_version: {schema_version!r}")

    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Every queue item must be an object")
        course_slug = item.get("course_slug")
        if not isinstance(course_slug, str) or not course_slug:
            raise ValueError("Every schema-v2 queue item requires course_slug")
    return migrated


def gap_id(course_slug: str, module: int, item: dict[str, object]) -> str:
    identity = item.get("coursera_item_id") or f"ORDER-{int(item['display_order']):02d}"
    return f"{course_slug}:M{module:02d}:{identity}"


def expected_paths(course_slug: str, module: int, item: dict[str, object]) -> tuple[str, str]:
    order = int(item["display_order"])
    slug = str(item["slug"])
    raw = f"raw/{course_slug}/module-{module:02d}/widgets/{order:02d}-{slug}/"
    readable = f"readable/{course_slug}/module-{module:02d}/widgets/{order:02d}-{slug}.md"
    return raw, readable


def create_entry(payload: dict[str, object], item: dict[str, object]) -> dict[str, object]:
    course_slug = str(payload["course_slug"])
    module = int(payload["module_number"])
    lock_state = item.get("is_locked")
    eligible = lock_state is False
    raw, readable = expected_paths(course_slug, module, item)
    is_lab = str(item["title"]).casefold().startswith("hands-on lab:")
    is_interactive_tool = item["type"] in {"ungradedLti", "coach"}
    verification = []
    if is_lab:
        verification.append("capture instructions/task structure only; do not fill or submit")
    verification += [
        "explicit false lock state before capture",
        "official attachments and API/iframe sources checked first",
        "complete body preserved",
        "source manifest contains bytes and SHA-256",
        "mechanical Markdown matches source",
    ]
    return {
        "gap_id": gap_id(course_slug, module, item),
        "course_slug": course_slug,
        "module": module,
        "display_order": item["display_order"],
        "item_id": item.get("coursera_item_id"),
        "title": item["title"],
        "type": item["type"],
        "slug": item["slug"],
        "is_locked": lock_state,
        "eligibility": "eligible_unlocked" if eligible else "unknown_until_inventory_refresh",
        "status": "manual_capture_pending" if eligible else "needs_inventory_refresh",
        "source_url": item.get("url"),
        "existing_sources": [f"module-{module:02d}/module_items.json inventory entry"],
        "missing_sources": [
            "complete body",
            "official attachment check",
            "API/iframe/source package/raw HTML",
            "browser-rendered or user-attested visible-text fallback if needed",
            "readable Markdown",
            "item source manifest",
        ],
        "next_manual_action": (
            "Use the logged-in browser only after authoritative source checks; capture lab instructions, task structure, and official assets without filling or submitting."
            if eligible and is_lab
            else "Capture static instructions and launch metadata only; do not start a coach conversation, transmit learner input, or submit an external tool."
            if eligible and is_interactive_tool
            else "Use the logged-in browser only after authoritative source checks; capture one representative static body before scaling."
            if eligible
            else "Refresh official inventory; do not capture until lock state is explicitly false."
        ),
        "expected_raw_dir": raw,
        "expected_readable_path": readable,
        "verification_required": verification,
        "last_checked": date.today().isoformat(),
    }


def count_items(items: list[dict[str, object]]) -> dict[str, int]:
    statuses = Counter(item["status"] for item in items)
    return {
        "total": len(items),
        "known_unlocked": sum(
            item.get("eligibility") == "eligible_unlocked" for item in items
        ),
        "manual_capture_pending": statuses["manual_capture_pending"],
        "partial_capture": statuses["partial_capture"],
        "needs_inventory_refresh": statuses["needs_inventory_refresh"],
        "captured_unverified": statuses["captured_unverified"],
        "verified": statuses["verified"],
        "blocked": statuses["blocked"],
    }


def recompute(data: dict[str, object]) -> None:
    items = data["items"]
    data["counts"] = count_items(items)
    course_slugs = sorted({str(item["course_slug"]) for item in items})
    data["course_counts"] = {
        course_slug: count_items(
            [item for item in items if item["course_slug"] == course_slug]
        )
        for course_slug in course_slugs
    }


def render_count_rows(counts: dict[str, int]) -> str:
    return f"""| Total tracked gaps | {counts['total']} |
| Known unlocked and eligible | {counts['known_unlocked']} |
| Manual capture pending | {counts['manual_capture_pending']} |
| Partial capture | {counts['partial_capture']} |
| Needs inventory refresh | {counts['needs_inventory_refresh']} |
| Captured unverified | {counts['captured_unverified']} |
| Verified | {counts['verified']} |
| Blocked | {counts['blocked']} |
| Open completion-gate states | {sum(counts[status] for status in OPEN_STATUSES)} |"""


def render_markdown(data: dict[str, object]) -> str:
    counts = data["counts"]
    item_rows = []
    for item in data["items"]:
        eligibility = "unlocked" if item.get("eligibility") == "eligible_unlocked" else "unknown"
        item_rows.append(
            f"| `{item['course_slug']}` | `{item['gap_id']}` | "
            f"M{item['module']} / {item['display_order']} | {item['title']} | "
            f"{eligibility} | `{item['status']}` | {item['next_manual_action']} |"
        )

    course_rows = []
    for course_slug, course_count in data["course_counts"].items():
        open_count = sum(course_count[status] for status in OPEN_STATUSES)
        course_rows.append(
            f"| `{course_slug}` | {course_count['total']} | "
            f"{course_count['known_unlocked']} | {course_count['verified']} | {open_count} |"
        )

    return f"""# Manual capture queue

Last updated: {data['last_updated']}  
Canonical machine-readable register: `manual_capture_queue.json`  
Schema: `{data['schema_version']}`  
Policy: `{data.get('policy', 'capture_policy.md')}`

## Current counts

| Measure | Count |
|---|---:|
{render_count_rows(counts)}

## Counts by course

| Course | Total gaps | Known unlocked | Verified | Open completion gates |
|---|---:|---:|---:|---:|
{chr(10).join(course_rows)}

## Item register

| Course | Gap ID | Module / order | Item | Eligibility | Status | Next action |
|---|---|---|---|---|---|---|
{chr(10).join(item_rows)}

Do not capture unknown or locked items. Keep verified entries as audit history.
Recompute this document from the JSON register after every capture attempt.
"""


def atomic_write(path: Path, data: str) -> None:
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(data, encoding="utf-8")
    temp.replace(path)


def write_queue(data: dict[str, object], queue_json: Path, queue_markdown: Path) -> None:
    data["last_updated"] = date.today().isoformat()
    data["status_definitions"] = STATUS_DEFINITIONS
    recompute(data)
    queue_json.parent.mkdir(parents=True, exist_ok=True)
    queue_markdown.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(queue_json, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    atomic_write(queue_markdown, render_markdown(data))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--migrate-only",
        action="store_true",
        help="upgrade and rerender an existing queue without refreshing item inventory",
    )
    parser.add_argument(
        "paths",
        nargs="+",
        help=(
            "MODULE_ITEMS_JSON QUEUE_JSON QUEUE_MD, or QUEUE_JSON QUEUE_MD "
            "with --migrate-only"
        ),
    )
    args = parser.parse_args()

    expected = 2 if args.migrate_only else 3
    if len(args.paths) != expected:
        parser.error(
            "--migrate-only requires QUEUE_JSON QUEUE_MD"
            if args.migrate_only
            else "requires MODULE_ITEMS_JSON QUEUE_JSON QUEUE_MD"
        )

    if args.migrate_only:
        module_items = None
        queue_json, queue_markdown = map(Path, args.paths)
    else:
        module_items, queue_json, queue_markdown = map(Path, args.paths)

    json_root = require_project_root(queue_json)
    markdown_root = require_project_root(queue_markdown)
    if json_root != markdown_root:
        raise RuntimeError("Queue JSON and Markdown must share one capture project root")
    print(f"project_root={json_root}")

    if args.migrate_only:
        if not queue_json.is_file():
            raise FileNotFoundError(f"Queue does not exist: {queue_json}")
        data = json.loads(queue_json.read_text(encoding="utf-8"))
        before = dict(data.get("counts", {}))
        migrated = migrate_queue(data)
        write_queue(data, queue_json, queue_markdown)
        print(
            json.dumps(
                {
                    "migrated_schema": migrated,
                    "before": before,
                    "after": data["counts"],
                    "course_counts": data["course_counts"],
                },
                indent=2,
            )
        )
        return

    payload = json.loads(module_items.read_text(encoding="utf-8"))
    course_slug = str(payload["course_slug"])
    if queue_json.exists():
        data = json.loads(queue_json.read_text(encoding="utf-8"))
        migrated = migrate_queue(data)
    else:
        data = new_queue()
        migrated = False

    before = dict(data.get("counts", {}))
    existing_by_id = {
        (item["course_slug"], item.get("module"), item.get("item_id")): item
        for item in data["items"]
        if item.get("item_id") is not None
    }
    existing_unknown = {
        (item["course_slug"], item.get("module"), item.get("display_order")): item
        for item in data["items"]
        if item.get("item_id") is None
    }

    module = int(payload["module_number"])
    for item in payload["items"]:
        if item.get("type") not in TRACKED_TYPES or item.get("is_locked") is True:
            continue
        existing = existing_by_id.get(
            (course_slug, module, item.get("coursera_item_id"))
        )
        if existing is None:
            existing = existing_unknown.get(
                (course_slug, module, item.get("display_order"))
            )
        if existing is None:
            data["items"].append(create_entry(payload, item))
            continue
        existing.update(
            {
                "course_slug": course_slug,
                "item_id": item.get("coursera_item_id"),
                "title": item["title"],
                "type": item["type"],
                "slug": item["slug"],
                "is_locked": item.get("is_locked"),
                "source_url": item.get("url"),
                "last_checked": date.today().isoformat(),
            }
        )
        if item.get("is_locked") is False and existing.get("status") == "needs_inventory_refresh":
            existing["eligibility"] = "eligible_unlocked"
            existing["status"] = "manual_capture_pending"
            existing["next_manual_action"] = create_entry(payload, item)[
                "next_manual_action"
            ]

    data["items"].sort(
        key=lambda item: (
            item["course_slug"],
            item["module"],
            item["display_order"],
            item["gap_id"],
        )
    )
    write_queue(data, queue_json, queue_markdown)
    print(
        json.dumps(
            {
                "migrated_schema": migrated,
                "before": before,
                "after": data["counts"],
                "course_counts": data["course_counts"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
