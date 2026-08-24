#!/usr/bin/env python3
"""Render a human-readable Markdown view from a captured transcript JSON.

The raw WebVTT and mechanical JSON/Markdown sidecars remain untouched. This
renderer only collapses cue line breaks and groups consecutive cues into
paragraphs; it does not summarize, rewrite, or correct transcript wording.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path

from capture_paths import require_project_root


SENTENCE_END_RE = re.compile(r"[.!?][\"'’”)]*$")


def seconds(timestamp: str) -> float:
    parts = timestamp.split(":")
    if len(parts) == 2:
        hours = "0"
        minutes, remainder = parts
    elif len(parts) == 3:
        hours, minutes, remainder = parts
    else:
        raise ValueError(f"Unsupported WebVTT timestamp: {timestamp}")
    return int(hours) * 3600 + int(minutes) * 60 + float(remainder)


def readable_time(timestamp: str) -> str:
    parts = timestamp.split(":")
    if len(parts) == 2:
        hours = "0"
        minutes, remainder = parts
    elif len(parts) == 3:
        hours, minutes, remainder = parts
    else:
        raise ValueError(f"Unsupported WebVTT timestamp: {timestamp}")
    whole_seconds = int(float(remainder))
    if int(hours):
        return f"{int(hours):02d}:{int(minutes):02d}:{whole_seconds:02d}"
    return f"{int(minutes):02d}:{whole_seconds:02d}"


def cue_text(cue: dict[str, object]) -> str:
    return " ".join(str(line).strip() for line in cue["text_lines"] if str(line).strip())


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def group_cues(cues: list[dict[str, object]]) -> list[list[dict[str, object]]]:
    groups: list[list[dict[str, object]]] = []
    current: list[dict[str, object]] = []
    word_count = 0

    for cue in cues:
        text = cue_text(cue)
        current.append(cue)
        word_count += len(text.split())
        duration = seconds(str(cue["end"])) - seconds(str(current[0]["start"]))

        # Prefer a complete sentence after a useful reading-sized span. The
        # hard limits prevent very long paragraphs when punctuation is sparse.
        natural_break = duration >= 18 and SENTENCE_END_RE.search(text)
        hard_break = duration >= 40 or word_count >= 105
        if natural_break or hard_break:
            groups.append(current)
            current = []
            word_count = 0

    if current:
        groups.append(current)
    return groups


def render(payload: dict[str, object]) -> str:
    lesson = payload["lesson"]
    cues = payload["cues"]
    groups = group_cues(cues)

    lines = [
        f"# {lesson['title']}",
        "",
        f"> **Module section:** {lesson['section']}  ",
        f"> **Lecture order:** {lesson['order']}  ",
        f"> **Duration:** {lesson.get('duration_displayed', 'unknown')}  ",
        f"> **Source:** `{payload['source_file']}`  ",
        f"> **Source SHA-256:** `{payload['source_sha256']}`",
        "",
        "> Readable derivative: cue line breaks collapsed and consecutive cues grouped. "
        "Wording is unchanged; use the VTT/JSON source for cue-level timestamps.",
        "",
        "## Transcript",
        "",
    ]

    for group in groups:
        start = readable_time(str(group[0]["start"]))
        end = readable_time(str(group[-1]["end"]))
        paragraph = " ".join(cue_text(cue) for cue in group)
        lines.extend([f"**[{start}–{end}]**", "", paragraph, ""])

    return "\n".join(lines).rstrip() + "\n"


def verify_no_text_loss(cues: list[dict[str, object]]) -> None:
    groups = group_cues(cues)
    source_text = " ".join(cue_text(cue) for cue in cues)
    grouped_text = " ".join(
        " ".join(cue_text(cue) for cue in group) for group in groups
    )
    if grouped_text != source_text:
        raise ValueError("Readable grouping changed or dropped transcript text")


def convert_one(source_json: Path, output_md: Path) -> dict[str, object]:
    payload = json.loads(source_json.read_text(encoding="utf-8"))
    cues = payload["cues"]
    verify_no_text_loss(cues)

    source_vtt = source_json.with_name(str(payload["source_file"]))
    if not source_vtt.is_file():
        raise FileNotFoundError(f"Missing source VTT: {source_vtt}")
    actual_source_hash = sha256(source_vtt)
    if actual_source_hash != payload["source_sha256"]:
        raise ValueError(f"Source VTT hash mismatch: {source_vtt}")

    if output_md.exists():
        raise FileExistsError(f"Refusing to overwrite {output_md}")
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(render(payload), encoding="utf-8")
    groups = group_cues(cues)
    return {
        "title": payload["lesson"]["title"],
        "lecture_order": payload["lesson"]["order"],
        "source_json": source_json.name,
        "source_vtt": source_vtt.name,
        "source_vtt_sha256": actual_source_hash,
        "cue_count": len(cues),
        "paragraph_count": len(groups),
        "output_md": output_md.name,
        "output_sha256": sha256(output_md),
        "text_preservation_verified": True,
    }


def convert_tree(source_root: Path, output_root: Path) -> None:
    source_paths = sorted(source_root.glob("module-*/transcripts/*.en.json"))
    if not source_paths:
        raise FileNotFoundError(f"No module transcript JSON files under {source_root}")

    entries: list[dict[str, object]] = []
    for source_json in source_paths:
        relative = source_json.relative_to(source_root)
        output_name = source_json.name.removesuffix(".en.json") + ".en.readable.md"
        output_md = output_root / relative.parent / output_name
        entry = convert_one(source_json, output_md)
        entry["module"] = relative.parts[0]
        entry["source_json_path"] = relative.as_posix()
        entry["output_md_path"] = output_md.relative_to(output_root).as_posix()
        entries.append(entry)
        print(
            f"verified module={entry['module']} order={entry['lecture_order']} "
            f"cues={entry['cue_count']} paragraphs={entry['paragraph_count']}"
        )

    manifest = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "conversion": (
            "readable derivative; cue line breaks collapsed and consecutive cues "
            "grouped; transcript wording unchanged"
        ),
        "source_root": str(source_root),
        "lesson_count": len(entries),
        "total_cue_count": sum(int(entry["cue_count"]) for entry in entries),
        "total_paragraph_count": sum(
            int(entry["paragraph_count"]) for entry in entries
        ),
        "all_source_vtt_hashes_verified": True,
        "all_text_preservation_checks_passed": True,
        "lessons": entries,
    }
    manifest_path = output_root / "readable_manifest.json"
    if manifest_path.exists():
        raise FileExistsError(f"Refusing to overwrite {manifest_path}")
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"complete lessons={len(entries)} cues={manifest['total_cue_count']} "
        f"paragraphs={manifest['total_paragraph_count']} manifest={manifest_path}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    project_root = require_project_root(args.output)
    print(f"project_root={project_root}")

    if args.source.is_dir():
        args.output.mkdir(parents=True, exist_ok=True)
        convert_tree(args.source, args.output)
    else:
        entry = convert_one(args.source, args.output)
        print(
            f"verified cues={entry['cue_count']} "
            f"paragraphs={entry['paragraph_count']} output={args.output}"
        )


if __name__ == "__main__":
    main()
