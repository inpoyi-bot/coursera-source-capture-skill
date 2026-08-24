#!/usr/bin/env python3
"""Capture Module readings from Coursera's cookie-free supplement APIs."""

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


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def get_response(session: requests.Session, url: str) -> requests.Response:
    response = session.get(url, timeout=30)
    response.raise_for_status()
    return response


def get_json(session: requests.Session, url: str) -> dict[str, object]:
    response = get_response(session, url)
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


def course_materials(session: requests.Session, slug: str) -> dict[str, object]:
    fields = (
        "moduleIds%2ConDemandCourseMaterialModules.v1(name%2Cslug%2ClessonIds)"
        "%2ConDemandCourseMaterialLessons.v1(name%2Cslug%2CitemIds)"
        "%2ConDemandCourseMaterialItems.v2(name%2Cslug%2CcontentSummary%2CisLocked)"
    )
    url = (
        f"{ROOT}/api/onDemandCourseMaterials.v2/?q=slug&slug={quote(slug)}"
        f"&includes=modules%2Clessons%2Citems&fields={fields}&showLockedItems=true"
    )
    return get_json(session, url)


def safe_name(value: str, fallback: str) -> str:
    name = Path(value or fallback).name
    name = re.sub(r"[^A-Za-z0-9._ -]+", "-", name).strip(" .-")
    return name or fallback


def extension_for(name: str, url: str, declared: str | None = None) -> str:
    if declared:
        return (declared if declared.startswith(".") else f".{declared}").lower()
    return (Path(name).suffix or Path(urlparse(url).path).suffix).lower()


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
    materials = course_materials(session, index["course_slug"])
    linked = materials.get("linked", {})
    if not isinstance(linked, dict):
        raise RuntimeError("Course materials response is missing linked data")

    modules = {item["id"]: item for item in linked["onDemandCourseMaterialModules.v1"]}
    lessons = {item["id"]: item for item in linked["onDemandCourseMaterialLessons.v1"]}
    items = {item["id"]: item for item in linked["onDemandCourseMaterialItems.v2"]}
    module_ids = materials["elements"][0]["moduleIds"]
    module_id = module_ids[int(index["module_number"]) - 1]
    module = modules[module_id]

    selected: list[dict[str, object]] = []
    skipped_locked = 0
    skipped_unknown = 0
    for lesson_id in module["lessonIds"]:
        lesson = lessons[lesson_id]
        for item_id in lesson["itemIds"]:
            item = items[item_id]
            if item["contentSummary"]["typeName"] != "supplement":
                continue
            lock_state = item.get("isLocked")
            if lock_state is False:
                selected.append({**item, "lesson_name": lesson["name"]})
            elif lock_state is True:
                skipped_locked += 1
            else:
                skipped_unknown += 1

    args.output_dir.mkdir(parents=True, exist_ok=True)
    inventory_path = args.output_dir / "reading_inventory.json"
    if inventory_path.exists():
        raise FileExistsError(f"Refusing to overwrite {inventory_path}")
    inventory: dict[str, object] = {
        "schema_version": 1,
        "inspection_method": "cookie-free official Coursera supplement APIs",
        "course_slug": index["course_slug"],
        "module_number": index["module_number"],
        "signed_or_ephemeral_urls_persisted": False,
        "readings": [],
    }
    attachment_count = 0

    for reading_order, item in enumerate(selected, start=1):
        item_id = item["id"]
        endpoint = (
            f"{ROOT}/api/onDemandSupplements.v1/"
            f"{quote(course_id, safe='')}~{quote(item_id, safe='')}"
            "?includes=asset&fields=openCourseAssets.v1(typeName)%2C"
            "openCourseAssets.v1(definition)"
        )
        response = get_response(session, endpoint)
        payload = response.json()
        if payload.get("errorCode"):
            raise RuntimeError(f"Reading {item_id}: {payload['errorCode']}")

        file_stem = f"{reading_order:02d}-{item['slug']}"
        raw_path = args.output_dir / f"{file_stem}.supplement.json"
        if raw_path.exists():
            raise FileExistsError(f"Refusing to overwrite {raw_path}")
        raw_path.write_bytes(response.content)
        record: dict[str, object] = {
            "order": reading_order,
            "lesson": item["lesson_name"],
            "title": item["name"],
            "coursera_item_id": item_id,
            "slug": item["slug"],
            "is_locked": item.get("isLocked"),
            "raw_api_file": raw_path.name,
            "raw_api_bytes": len(response.content),
            "raw_api_sha256": sha256(response.content),
            "cml_files": [],
            "renderable_metadata_files": [],
            "attachments": [],
        }

        supplement_linked = payload.get("linked", {})
        assets = (
            supplement_linked.get("openCourseAssets.v1", [])
            if isinstance(supplement_linked, dict)
            else []
        )
        asset_ids: list[str] = []
        direct_assets: list[dict[str, object]] = []
        cml_number = 0

        for asset in assets:
            if not isinstance(asset, dict):
                continue
            definition = asset.get("definition", {})
            definition = definition if isinstance(definition, dict) else {}
            type_name = asset.get("typeName")
            if type_name == "cml" and isinstance(definition.get("value"), str):
                cml_number += 1
                suffix = "" if cml_number == 1 else f"-{cml_number}"
                cml_path = args.output_dir / f"{file_stem}{suffix}.cml"
                if cml_path.exists():
                    raise FileExistsError(f"Refusing to overwrite {cml_path}")
                cml_data = definition["value"].encode("utf-8")
                cml_path.write_bytes(cml_data)
                record["cml_files"].append(
                    {
                        "path": cml_path.name,
                        "bytes": len(cml_data),
                        "sha256": sha256(cml_data),
                    }
                )
                renderable = definition.get("renderableHtmlWithMetadata")
                if renderable is not None:
                    renderable_path = (
                        args.output_dir / f"{file_stem}{suffix}.renderable.json"
                    )
                    if renderable_path.exists():
                        raise FileExistsError(
                            f"Refusing to overwrite {renderable_path}"
                        )
                    renderable_data = (
                        json.dumps(renderable, ensure_ascii=False, indent=2) + "\n"
                    ).encode("utf-8")
                    renderable_path.write_bytes(renderable_data)
                    record["renderable_metadata_files"].append(
                        {
                            "path": renderable_path.name,
                            "bytes": len(renderable_data),
                            "sha256": sha256(renderable_data),
                        }
                    )
            elif type_name == "asset" and isinstance(definition.get("assetId"), str):
                asset_ids.append(definition["assetId"])
            elif type_name == "url" and isinstance(definition.get("url"), str):
                direct_assets.append(
                    {
                        "name": definition.get("name") or "linked-resource",
                        "url": definition["url"],
                        "declared_extension": None,
                    }
                )

        if asset_ids:
            ids = quote(",".join(asset_ids), safe=",")
            asset_payload = get_json(
                session,
                f"{ROOT}/api/assets.v1?ids={ids}&fields=fileExtension%2Ctags",
            )
            for asset in asset_payload.get("elements", []):
                if not isinstance(asset, dict):
                    continue
                url_value = asset.get("url", {})
                url_value = url_value.get("url") if isinstance(url_value, dict) else None
                if isinstance(url_value, str):
                    direct_assets.append(
                        {
                            "name": asset.get("name") or "attachment",
                            "url": url_value,
                            "declared_extension": asset.get("fileExtension"),
                        }
                    )

        for attachment in direct_assets:
            extension = extension_for(
                str(attachment["name"]),
                str(attachment["url"]),
                attachment.get("declared_extension"),
            )
            filename = safe_name(str(attachment["name"]), f"attachment{extension}")
            if extension and not filename.lower().endswith(extension):
                filename += extension
            attachment_record: dict[str, object] = {
                "name": filename,
                "extension": extension or None,
                "downloaded": False,
            }
            if extension in ALLOWED_EXTENSIONS:
                attachment_response = get_response(session, str(attachment["url"]))
                attachment_path = args.output_dir / "attachments" / file_stem / filename
                if attachment_path.exists():
                    raise FileExistsError(
                        f"Refusing to overwrite {attachment_path}"
                    )
                attachment_path.parent.mkdir(parents=True, exist_ok=True)
                attachment_path.write_bytes(attachment_response.content)
                attachment_record.update(
                    {
                        "downloaded": True,
                        "local_path": attachment_path.relative_to(args.output_dir).as_posix(),
                        "bytes": len(attachment_response.content),
                        "sha256": sha256(attachment_response.content),
                    }
                )
                attachment_count += 1
            else:
                attachment_record["reason"] = (
                    "not a PPT/PPTX/PDF/lecture-note extension"
                )
            record["attachments"].append(attachment_record)

        inventory["readings"].append(record)
        print(
            f"order={reading_order:02d} id={item_id} cml={len(record['cml_files'])} "
            f"attachments={len(record['attachments'])}"
        )

    inventory_path.write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"readings_captured={len(selected)}")
    print(f"readings_skipped_locked={skipped_locked}")
    print(f"readings_skipped_lock_unknown={skipped_unknown}")
    print(f"attachments_downloaded={attachment_count}")
    print(f"inventory={inventory_path}")


if __name__ == "__main__":
    main()
