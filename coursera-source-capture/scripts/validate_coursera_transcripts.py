#!/usr/bin/env python3
"""Mechanically validate captured Coursera VTT and generated sidecars."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from capture_paths import require_project_root
from vtt_to_markdown import markdown_for, parse_vtt


def milliseconds(timestamp: str) -> int:
    parts = timestamp.split(":")
    if len(parts) == 2:
        hours = "0"
        minutes, seconds_ms = parts
    elif len(parts) == 3:
        hours, minutes, seconds_ms = parts
    else:
        raise ValueError(f"Unsupported WebVTT timestamp: {timestamp}")
    seconds, millis = seconds_ms.split(".")
    return (
        int(hours) * 3_600_000
        + int(minutes) * 60_000
        + int(seconds) * 1_000
        + int(millis)
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("transcripts_dir", type=Path)
    parser.add_argument("lesson_index", type=Path)
    parser.add_argument("--start-order", type=int, default=1)
    parser.add_argument("--end-order", type=int)
    args = parser.parse_args()

    project_root = require_project_root(args.transcripts_dir)
    print(f"project_root={project_root}")

    index = json.loads(args.lesson_index.read_text(encoding="utf-8"))
    lectures = index["video_lectures"]
    end_order = args.end_order or max(item["order"] for item in lectures)
    selected = [
        item
        for item in lectures
        if args.start_order <= int(item["order"]) <= end_order
        and item.get("is_locked") is False
    ]
    in_range = [
        item for item in lectures if args.start_order <= int(item["order"]) <= end_order
    ]
    skipped_locked = sum(item.get("is_locked") is True for item in in_range)
    skipped_unknown = sum(item.get("is_locked") is not True and item.get("is_locked") is not False for item in in_range)

    failures: list[str] = []
    print("order\tcues\tfirst\tlast\tbytes\tsha256\tfile")
    for lecture in selected:
        stem = lecture["file_stem"]
        vtt_path = args.transcripts_dir / f"{stem}.en.vtt"
        json_path = args.transcripts_dir / f"{stem}.en.json"
        md_path = args.transcripts_dir / f"{stem}.en.md"
        missing = [str(path) for path in (vtt_path, json_path, md_path) if not path.exists()]
        if missing:
            failures.append(f"order {lecture['order']}: missing {', '.join(missing)}")
            continue

        raw = vtt_path.read_bytes()
        source_hash = sha256(vtt_path)
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        cues = payload.get("cues", [])
        parsed_header, parsed_cues = parse_vtt(vtt_path)
        cue_indices = [cue.get("cue_index") for cue in cues]
        expected_indices = list(range(1, len(cues) + 1))
        starts = [milliseconds(cue["start"]) for cue in cues]
        ends = [milliseconds(cue["end"]) for cue in cues]

        checks = {
            "WEBVTT header": raw.startswith((b"WEBVTT", b"\xef\xbb\xbfWEBVTT")),
            "non-empty cues": bool(cues)
            and all(any(line.strip() for line in cue["text_lines"]) for cue in cues),
            "sequential mechanical cue indices": cue_indices == expected_indices,
            "valid cue ranges": all(start <= end for start, end in zip(starts, ends)),
            "monotonic starts": starts == sorted(starts),
            "no truncation marker": b"[truncated for batch processing]" not in raw,
            "source hash matches": payload.get("source_sha256") == source_hash,
            "JSON header matches raw VTT": payload.get("webvtt_header_lines")
            == parsed_header,
            "JSON cues match raw VTT": cues == parsed_cues,
            "raw Markdown matches mechanical render": md_path.read_text(encoding="utf-8")
            == markdown_for(vtt_path, lecture, parsed_cues, source_hash),
            "lesson mapping matches": payload.get("lesson", {}).get("order")
            == lecture["order"]
            and payload.get("lesson", {}).get("coursera_item_id")
            == lecture["coursera_item_id"]
            and payload.get("lesson", {}).get("title") == lecture["title"],
        }
        for label, passed in checks.items():
            if not passed:
                failures.append(f"order {lecture['order']}: {label} failed")

        first = cues[0]["start"] if cues else "missing"
        last = cues[-1]["end"] if cues else "missing"
        print(
            f"{lecture['order']}\t{len(cues)}\t{first}\t{last}\t{len(raw)}\t"
            f"{source_hash}\t{vtt_path.name}"
        )

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        raise SystemExit(1)
    print(f"validated={len(selected)}")
    print(f"skipped_locked={skipped_locked}")
    print(f"skipped_lock_unknown={skipped_unknown}")


if __name__ == "__main__":
    main()
