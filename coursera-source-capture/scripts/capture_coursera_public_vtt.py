#!/usr/bin/env python3
"""Capture official English WebVTT from Coursera's cookie-free public APIs."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import quote

import requests

from capture_paths import require_project_root


ROOT = "https://www.coursera.org"


def get_json(session: requests.Session, url: str) -> dict[str, object]:
    response = session.get(url, timeout=30)
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload, dict) and payload.get("errorCode"):
        raise RuntimeError(f"Coursera API error: {payload['errorCode']}")
    return payload


def course_id(session: requests.Session, slug: str) -> str:
    url = (
        f"{ROOT}/api/onDemandCourses.v1?q=slug&slug={quote(slug)}"
        "&fields=name,slug,isRestrictedMembership"
    )
    payload = get_json(session, url)
    elements = payload.get("elements", [])
    if not isinstance(elements, list) or len(elements) != 1:
        raise RuntimeError(f"Expected one course for slug {slug!r}")
    course = elements[0]
    if not isinstance(course, dict) or not isinstance(course.get("id"), str):
        raise RuntimeError("Course response is missing id")
    return course["id"]


def english_vtt_url(
    session: requests.Session, course_id_value: str, lecture_id: str
) -> str:
    fields = "onDemandVideos.v1(sources%2Csubtitles%2CsubtitlesVtt%2CsubtitlesTxt)"
    url = (
        f"{ROOT}/api/onDemandLectureVideos.v1/"
        f"{quote(course_id_value, safe='')}~{quote(lecture_id, safe='')}"
        f"?includes=video&fields={fields}"
    )
    payload = get_json(session, url)
    linked = payload.get("linked", {})
    videos = linked.get("onDemandVideos.v1", []) if isinstance(linked, dict) else []
    if not isinstance(videos, list) or len(videos) != 1:
        raise RuntimeError(f"Lecture {lecture_id}: expected one linked video")
    video = videos[0]
    tracks = video.get("subtitlesVtt", {}) if isinstance(video, dict) else {}
    source = tracks.get("en") if isinstance(tracks, dict) else None
    if not isinstance(source, str) or not source:
        raise RuntimeError(f"Lecture {lecture_id}: English subtitlesVtt is missing")
    return f"{ROOT}{source}" if source.startswith("/") else source


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("lesson_index", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--start-order", type=int, default=1)
    parser.add_argument("--end-order", type=int)
    args = parser.parse_args()

    project_root = require_project_root(args.output_dir)
    print(f"project_root={project_root}")

    index = json.loads(args.lesson_index.read_text(encoding="utf-8"))
    slug = index["course_slug"]
    lectures = index["video_lectures"]
    end_order = args.end_order or max(item["order"] for item in lectures)

    args.output_dir.mkdir(parents=True, exist_ok=True)

    session: requests.Session | None = None
    resolved_course_id: str | None = None
    captured = 0
    skipped_locked = 0
    skipped_unknown = 0
    for lecture in lectures:
        order = int(lecture["order"])
        if not args.start_order <= order <= end_order:
            continue
        lock_state = lecture.get("is_locked")
        if lock_state is True:
            print(f"skip order={order:02d} reason=locked")
            skipped_locked += 1
            continue
        if lock_state is not False:
            print(f"skip order={order:02d} reason=lock_state_unknown")
            skipped_unknown += 1
            continue
        if session is None:
            session = requests.Session()
            session.trust_env = False
            resolved_course_id = course_id(session, slug)
        lecture_id = str(lecture["coursera_item_id"])
        assert resolved_course_id is not None
        source = english_vtt_url(session, resolved_course_id, lecture_id)
        response = session.get(source, timeout=30)
        response.raise_for_status()
        data = response.content
        if not data.startswith((b"WEBVTT", b"\xef\xbb\xbfWEBVTT")):
            raise RuntimeError(f"Lecture {lecture_id}: response lacks WEBVTT header")
        if b"[truncated for batch processing]" in data:
            raise RuntimeError(f"Lecture {lecture_id}: truncation marker found")

        path = args.output_dir / f"{lecture['file_stem']}.en.vtt"
        if path.exists():
            raise FileExistsError(path)
        path.write_bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        print(
            f"order={order:02d} id={lecture_id} bytes={len(data)} "
            f"sha256={digest} file={path.name}"
        )
        captured += 1

    print(f"captured={captured}")
    print(f"skipped_locked={skipped_locked}")
    print(f"skipped_lock_unknown={skipped_unknown}")


if __name__ == "__main__":
    main()
