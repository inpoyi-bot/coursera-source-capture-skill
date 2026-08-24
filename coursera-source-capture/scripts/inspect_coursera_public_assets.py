#!/usr/bin/env python3
"""Inspect and capture official Coursera lecture attachments without cookies."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import quote, urlparse

import requests

from capture_paths import require_project_root


ROOT = "https://www.coursera.org"
ALLOWED_EXTENSIONS = {".ppt", ".pptx", ".pdf", ".doc", ".docx", ".rtf", ".txt"}


def get_json(session: requests.Session, url: str) -> dict[str, object]:
    response = session.get(url, timeout=30)
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload, dict) and payload.get("errorCode"):
        raise RuntimeError(f"Coursera API error: {payload['errorCode']}")
    return payload


def resolve_course_id(session: requests.Session, slug: str) -> str:
    payload = get_json(
        session,
        f"{ROOT}/api/onDemandCourses.v1?q=slug&slug={quote(slug)}&fields=name,slug",
    )
    elements = payload.get("elements", [])
    if not isinstance(elements, list) or len(elements) != 1:
        raise RuntimeError(f"Expected one course for slug {slug!r}")
    value = elements[0].get("id")
    if not isinstance(value, str):
        raise RuntimeError("Course response is missing id")
    return value


def safe_name(name: str, fallback: str) -> str:
    value = Path(name or fallback).name
    value = re.sub(r"[^A-Za-z0-9._ -]+", "-", value).strip(" .-")
    return value or fallback


def extension_for(name: str, url: str, declared: str | None = None) -> str:
    if declared:
        value = declared if declared.startswith(".") else f".{declared}"
        return value.lower()
    suffix = Path(name).suffix or Path(urlparse(url).path).suffix
    return suffix.lower()


def download_attachment(
    session: requests.Session,
    url: str,
    destination: Path,
) -> tuple[int, str]:
    if destination.exists():
        raise FileExistsError(f"Refusing to overwrite {destination}")
    response = session.get(url, timeout=60)
    response.raise_for_status()
    data = response.content
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    return len(data), hashlib.sha256(data).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("lesson_index", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()

    project_root = require_project_root(args.output_dir)
    print(f"project_root={project_root}")

    index = json.loads(args.lesson_index.read_text(encoding="utf-8"))
    session = requests.Session()
    session.trust_env = False
    course_id = resolve_course_id(session, index["course_slug"])

    inventory: dict[str, object] = {
        "schema_version": 1,
        "inspection_method": "cookie-free official Coursera lecture-assets APIs",
        "course_slug": index["course_slug"],
        "module_number": index["module_number"],
        "signed_or_ephemeral_urls_persisted": False,
        "lectures": [],
    }
    downloaded = 0
    exposed = 0
    skipped_locked = 0
    skipped_unknown = 0

    for lecture in index["video_lectures"]:
        lock_state = lecture.get("is_locked")
        if lock_state is True:
            skipped_locked += 1
            continue
        if lock_state is not False:
            skipped_unknown += 1
            continue
        lecture_id = lecture["coursera_item_id"]
        endpoint = (
            f"{ROOT}/api/onDemandLectureAssets.v1/"
            f"{quote(course_id, safe='')}~{quote(lecture_id, safe='')}/"
            "?includes=openCourseAssets"
        )
        payload = get_json(session, endpoint)
        linked = payload.get("linked", {})
        raw_assets = linked.get("openCourseAssets.v1", []) if isinstance(linked, dict) else []
        if not isinstance(raw_assets, list):
            raise RuntimeError(f"Lecture {lecture_id}: malformed asset list")

        lecture_record: dict[str, object] = {
            "order": lecture["order"],
            "title": lecture["title"],
            "coursera_item_id": lecture_id,
            "checked": True,
            "assets": [],
        }
        materialized: list[dict[str, object]] = []
        asset_ids: list[str] = []

        for raw in raw_assets:
            if not isinstance(raw, dict):
                continue
            definition = raw.get("definition", {})
            definition = definition if isinstance(definition, dict) else {}
            type_name = raw.get("typeName")
            if type_name == "asset" and isinstance(definition.get("assetId"), str):
                asset_ids.append(definition["assetId"])
            elif type_name == "url" and isinstance(definition.get("url"), str):
                materialized.append(
                    {
                        "type": "url",
                        "id": raw.get("id"),
                        "name": definition.get("name") or "linked-resource",
                        "url": definition["url"],
                        "declared_extension": None,
                    }
                )
            else:
                lecture_record["assets"].append(
                    {
                        "type": str(type_name or "unknown"),
                        "name": definition.get("name"),
                        "downloaded": False,
                        "reason": "unsupported lecture-asset record type",
                    }
                )

        if asset_ids:
            ids = quote(",".join(asset_ids), safe=",")
            assets_payload = get_json(
                session,
                f"{ROOT}/api/assets.v1?ids={ids}&fields="
                "audioSourceUrls%2CvideoSourceUrls%2CvideoThumbnailUrls%2C"
                "fileExtension%2Ctags",
            )
            for asset in assets_payload.get("elements", []):
                if not isinstance(asset, dict):
                    continue
                url_value = asset.get("url", {})
                url_value = url_value.get("url") if isinstance(url_value, dict) else None
                if not isinstance(url_value, str):
                    lecture_record["assets"].append(
                        {
                            "type": "asset",
                            "name": asset.get("name"),
                            "downloaded": False,
                            "reason": "asset response is missing download URL",
                        }
                    )
                    continue
                materialized.append(
                    {
                        "type": "asset",
                        "id": asset.get("id"),
                        "name": asset.get("name") or "attachment",
                        "url": url_value,
                        "declared_extension": asset.get("fileExtension"),
                    }
                )

        for asset in materialized:
            exposed += 1
            extension = extension_for(
                str(asset["name"]),
                str(asset["url"]),
                asset.get("declared_extension"),
            )
            filename = safe_name(str(asset["name"]), f"attachment{extension}")
            if extension and not filename.lower().endswith(extension):
                filename += extension
            record: dict[str, object] = {
                "type": asset["type"],
                "name": filename,
                "extension": extension or None,
                "downloaded": False,
            }
            if extension in ALLOWED_EXTENSIONS:
                relative = Path("slides") / f"{int(lecture['order']):02d}" / filename
                size, digest = download_attachment(
                    session, str(asset["url"]), args.output_dir / relative
                )
                record.update(
                    {
                        "downloaded": True,
                        "local_path": relative.as_posix(),
                        "bytes": size,
                        "sha256": digest,
                    }
                )
                downloaded += 1
            else:
                record["reason"] = "not a PPT/PPTX/PDF/lecture-note extension"
            lecture_record["assets"].append(record)

        inventory["lectures"].append(lecture_record)
        print(
            f"order={int(lecture['order']):02d} exposed={len(lecture_record['assets'])} "
            f"downloaded={sum(1 for item in lecture_record['assets'] if item.get('downloaded'))}"
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    inventory_path = args.output_dir / "lecture_assets_inventory.json"
    if inventory_path.exists():
        raise FileExistsError(f"Refusing to overwrite {inventory_path}")
    inventory_path.write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"assets_exposed={exposed}")
    print(f"attachments_downloaded={downloaded}")
    print(f"lectures_skipped_locked={skipped_locked}")
    print(f"lectures_skipped_lock_unknown={skipped_unknown}")
    print(f"inventory={inventory_path}")


if __name__ == "__main__":
    main()
