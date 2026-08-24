#!/usr/bin/env python3
"""Build a deterministic module item/video index from public Coursera APIs."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import quote

import requests

from capture_paths import require_project_root


ROOT = "https://www.coursera.org"


def normalized(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def explicit_lock_state(item: dict[str, object]) -> bool | None:
    """Return only an explicit boolean lock state; never infer unlocked."""
    value = item.get("isLocked")
    return value if isinstance(value, bool) else None


def get_json(session: requests.Session, url: str) -> dict[str, object]:
    response = session.get(url, timeout=30)
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload, dict) and payload.get("errorCode"):
        raise RuntimeError(f"Coursera API error: {payload['errorCode']}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("course_slug")
    parser.add_argument("module_number", type=int)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()

    project_root = require_project_root(args.output_dir)
    print(f"project_root={project_root}")

    session = requests.Session()
    session.trust_env = False
    course_payload = get_json(
        session,
        f"{ROOT}/api/onDemandCourses.v1?q=slug&slug={quote(args.course_slug)}"
        "&fields=name,slug,isRestrictedMembership",
    )
    course_elements = course_payload.get("elements", [])
    if not isinstance(course_elements, list) or len(course_elements) != 1:
        raise RuntimeError("Expected exactly one course")
    course = course_elements[0]

    fields = (
        "moduleIds%2ConDemandCourseMaterialModules.v1(name%2Cslug%2ClessonIds)"
        "%2ConDemandCourseMaterialLessons.v1(name%2Cslug%2CitemIds)"
        "%2ConDemandCourseMaterialItems.v2(name%2Cslug%2CtimeCommitment%2C"
        "contentSummary%2CisLocked)"
    )
    materials = get_json(
        session,
        f"{ROOT}/api/onDemandCourseMaterials.v2/?q=slug&slug="
        f"{quote(args.course_slug)}&includes=modules%2Clessons%2Citems"
        f"&fields={fields}&showLockedItems=true",
    )
    linked = materials.get("linked", {})
    if not isinstance(linked, dict):
        raise RuntimeError("Course materials response is missing linked data")

    modules = {item["id"]: item for item in linked["onDemandCourseMaterialModules.v1"]}
    lessons = {item["id"]: item for item in linked["onDemandCourseMaterialLessons.v1"]}
    items = {item["id"]: item for item in linked["onDemandCourseMaterialItems.v2"]}
    module_ids = materials["elements"][0]["moduleIds"]
    if not 1 <= args.module_number <= len(module_ids):
        raise RuntimeError(f"Module number {args.module_number} is out of range")
    module_id = module_ids[args.module_number - 1]
    module = modules[module_id]

    module_items: list[dict[str, object]] = []
    videos: list[dict[str, object]] = []
    display_order = 0
    video_order = 0
    for lesson_id in module["lessonIds"]:
        lesson = lessons[lesson_id]
        section = normalized(lesson["name"])
        for item_id in lesson["itemIds"]:
            item = items[item_id]
            display_order += 1
            type_name = item["contentSummary"]["typeName"]
            title = normalized(item["name"])
            is_locked = explicit_lock_state(item)
            stable_url = (
                f"{ROOT}/learn/{args.course_slug}/{type_name}/{item_id}/"
                f"{item['slug']}"
            )
            record = {
                "display_order": display_order,
                "section": section,
                "title": title,
                "coursera_item_id": item_id,
                "slug": item["slug"],
                "type": type_name,
                "is_locked": is_locked,
                "time_commitment_ms": item.get("timeCommitment"),
                "url": stable_url,
            }
            module_items.append(record)
            if type_name == "lecture":
                video_order += 1
                duration_ms = item.get("contentSummary", {}).get("definition", {}).get(
                    "duration"
                )
                duration_minutes = (
                    max(1, int(duration_ms) // 60_000)
                    if isinstance(duration_ms, (int, float))
                    else None
                )
                videos.append(
                    {
                        "order": video_order,
                        "section": section,
                        "title": title,
                        "coursera_item_id": item_id,
                        "display_order": display_order,
                        "is_locked": is_locked,
                        "duration_displayed": (
                            f"{duration_minutes} min" if duration_minutes else None
                        ),
                        "url": stable_url,
                        "file_stem": f"{video_order:02d}-{item['slug']}",
                    }
                )

    lesson_index = {
        "schema_version": 1,
        "course_title": normalized(course["name"]),
        "course_slug": args.course_slug,
        "module_number": args.module_number,
        "module_title": normalized(module["name"]),
        "source_outline_url": (
            f"{ROOT}/learn/{args.course_slug}/home/module/{args.module_number}"
        ),
        "video_lectures": videos,
    }
    item_index = {
        "schema_version": 1,
        "course_title": normalized(course["name"]),
        "course_slug": args.course_slug,
        "module_number": args.module_number,
        "module_title": normalized(module["name"]),
        "source": "cookie-free official Coursera course-materials API",
        "items": module_items,
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    lesson_index_path = args.output_dir / "lesson_index.json"
    item_index_path = args.output_dir / "module_items.json"
    existing = [path for path in (lesson_index_path, item_index_path) if path.exists()]
    if existing:
        raise FileExistsError(
            "Refusing to overwrite indexes: " + ", ".join(str(path) for path in existing)
        )
    lesson_index_path.write_text(
        json.dumps(lesson_index, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    item_index_path.write_text(
        json.dumps(item_index, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    type_counts: dict[str, int] = {}
    for item in module_items:
        type_counts[item["type"]] = type_counts.get(item["type"], 0) + 1
    print(f"module_id={module_id}")
    print(f"module_title={lesson_index['module_title']}")
    print(f"items={len(module_items)}")
    print(f"videos={len(videos)}")
    print(f"videos_unlocked={sum(item['is_locked'] is False for item in videos)}")
    print(f"videos_lock_unknown={sum(item['is_locked'] is None for item in videos)}")
    print("type_counts=" + json.dumps(type_counts, sort_keys=True))


if __name__ == "__main__":
    main()
