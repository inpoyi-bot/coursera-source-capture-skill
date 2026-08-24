#!/usr/bin/env python3
"""Create timestamp-preserving Markdown and JSON sidecars from raw WebVTT.

This is a mechanical source conversion. The input VTT is never modified and cue
text is not summarized, normalized, merged, or rewritten.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from capture_paths import require_project_root


TIMING_RE = re.compile(
    r"^(?P<start>(?:\d{2,}:)?\d{2}:\d{2}\.\d{3})\s+-->\s+"
    r"(?P<end>(?:\d{2,}:)?\d{2}:\d{2}\.\d{3})(?P<settings>.*)$"
)


def parse_vtt(path: Path) -> tuple[list[str], list[dict[str, object]]]:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    if not lines or lines[0].strip() != "WEBVTT":
        raise ValueError(f"{path}: missing WEBVTT header")

    header: list[str] = []
    cues: list[dict[str, object]] = []
    index = 1

    # WebVTT header metadata ends at the first blank line. Cue blocks then use
    # either [timing, text...] or [original cue id, timing, text...].
    while index < len(lines) and lines[index].strip() != "":
        header.append(lines[index])
        index += 1
    while index < len(lines) and lines[index].strip() == "":
        index += 1

    while index < len(lines):
        block: list[str] = []
        while index < len(lines) and lines[index].strip() != "":
            block.append(lines[index])
            index += 1
        while index < len(lines) and lines[index].strip() == "":
            index += 1
        if not block:
            continue

        first = block[0].strip()
        timing_position = 0 if TIMING_RE.match(first) else 1
        if timing_position >= len(block):
            header.extend(block)
            continue
        timing_match = TIMING_RE.match(block[timing_position].strip())
        if timing_match is None:
            # NOTE/STYLE/REGION and unknown non-cue blocks are preserved rather
            # than misclassified as transcript text.
            header.extend(block)
            continue
        cue_id = block[0] if timing_position == 1 else None
        cues.append(
            {
                "cue_index": len(cues) + 1,
                "cue_id": cue_id,
                "start": timing_match.group("start"),
                "end": timing_match.group("end"),
                "settings": timing_match.group("settings").strip(),
                "text_lines": block[timing_position + 1 :],
            }
        )

    return header, cues


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def lesson_for_stem(index: dict[str, object], stem: str) -> dict[str, object]:
    lectures = index.get("video_lectures", [])
    for lecture in lectures:
        if isinstance(lecture, dict) and lecture.get("file_stem") == stem:
            return lecture
    raise KeyError(f"No lesson_index entry for {stem}")


def markdown_for(
    vtt_path: Path,
    lesson: dict[str, object],
    cues: list[dict[str, object]],
    source_hash: str,
) -> str:
    lines = [
        f"# {lesson['title']}",
        "",
        f"- Section: {lesson['section']}",
        f"- Lecture order: {lesson['order']}",
        f"- Source: `{vtt_path.name}`",
        f"- Source SHA-256: `{source_hash}`",
        "- Conversion: mechanical WebVTT cue parse; source text unchanged",
        "",
        "## Timestamped transcript",
        "",
    ]
    for cue in cues:
        cue_text = "\n".join(cue["text_lines"])
        lines.extend([f"**{cue['start']} --> {cue['end']}**", "", cue_text, ""])
    return "\n".join(lines)


def write_sidecars(vtt_path: Path, lesson: dict[str, object]) -> None:
    header, cues = parse_vtt(vtt_path)
    source_hash = sha256(vtt_path)
    stem = vtt_path.name.removesuffix(".en.vtt")
    json_path = vtt_path.with_name(f"{stem}.en.json")
    md_path = vtt_path.with_name(f"{stem}.en.md")
    existing = [path for path in (json_path, md_path) if path.exists()]
    if existing:
        raise FileExistsError(
            "Refusing to overwrite sidecars: " + ", ".join(str(path) for path in existing)
        )

    payload = {
        "schema_version": 1,
        "conversion": "mechanical WebVTT cue parse; source text unchanged",
        "source_file": vtt_path.name,
        "source_sha256": source_hash,
        "lesson": lesson,
        "webvtt_header_lines": header,
        "cue_count": len(cues),
        "cues": cues,
    }
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    md_path.write_text(
        markdown_for(vtt_path, lesson, cues, source_hash), encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("transcripts_dir", type=Path)
    parser.add_argument("lesson_index", type=Path)
    args = parser.parse_args()

    project_root = require_project_root(args.transcripts_dir)
    print(f"project_root={project_root}")

    index = json.loads(args.lesson_index.read_text(encoding="utf-8"))
    vtt_paths = sorted(args.transcripts_dir.glob("*.en.vtt"))
    if not vtt_paths:
        raise SystemExit("No *.en.vtt files found")

    for vtt_path in vtt_paths:
        stem = vtt_path.name.removesuffix(".en.vtt")
        lesson = lesson_for_stem(index, stem)
        write_sidecars(vtt_path, lesson)
        print(f"converted {vtt_path.name}")


if __name__ == "__main__":
    main()
