#!/usr/bin/env python3
"""Save one explicitly unlocked widget's official course-materials item object."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import quote

import requests

from capture_paths import require_project_root


ROOT = "https://www.coursera.org"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("course_slug")
    parser.add_argument("item_id")
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()

    project_root = require_project_root(args.output_dir)
    print(f"project_root={project_root}")

    fields = (
        "moduleIds%2ConDemandCourseMaterialModules.v1(name%2Cslug%2ClessonIds)"
        "%2ConDemandCourseMaterialLessons.v1(name%2Cslug%2CitemIds)"
        "%2ConDemandCourseMaterialItems.v2(name%2Cslug%2CtimeCommitment%2C"
        "contentSummary%2CisLocked)"
    )
    url = (
        f"{ROOT}/api/onDemandCourseMaterials.v2/?q=slug&slug="
        f"{quote(args.course_slug)}&includes=modules%2Clessons%2Citems"
        f"&fields={fields}&showLockedItems=true"
    )
    session = requests.Session()
    session.trust_env = False
    response = session.get(url, timeout=30)
    response.raise_for_status()
    payload = response.json()
    if payload.get("errorCode"):
        raise RuntimeError(f"Coursera API error: {payload['errorCode']}")
    records = payload.get("linked", {}).get("onDemandCourseMaterialItems.v2", [])
    matches = [item for item in records if item.get("id") == args.item_id]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one item object for {args.item_id!r}")
    item = matches[0]
    if item.get("isLocked") is not False:
        raise RuntimeError("Refusing metadata capture unless isLocked is explicitly false")
    if item.get("contentSummary", {}).get("typeName") not in {
        "ungradedWidget",
        "ungradedPlugin",
        "ungradedLti",
        "coach",
    }:
        raise RuntimeError("Item is not a supported interactive source type")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / "official-item-api.json"
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite {output}")
    data = (json.dumps(item, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    output.write_bytes(data)
    definition = item.get("contentSummary", {}).get("definition", {})
    print(json.dumps({
        "path": str(output),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "item_id": item["id"],
        "type": item["contentSummary"]["typeName"],
        "is_locked": item["isLocked"],
        "definition_keys": sorted(definition) if isinstance(definition, dict) else [],
        "capture_status": "partial_capture_metadata_only",
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
