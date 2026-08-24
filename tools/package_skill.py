#!/usr/bin/env python3
"""Build a deterministic zip containing only the installable skill directory."""

from __future__ import annotations

import argparse
import hashlib
import re
import zipfile
from pathlib import Path


SKIP_PARTS = {"__pycache__", ".DS_Store"}
ALLOWED_TOP_LEVEL = {"SKILL.md", "agents", "references", "scripts"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--skill-dir", type=Path, default=Path("coursera-source-capture"))
    parser.add_argument("--output-dir", type=Path, default=Path("dist"))
    args = parser.parse_args()

    version = args.version.removeprefix("v")
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?", version):
        raise SystemExit(f"Invalid version: {args.version}")
    skill_dir = args.skill_dir.resolve()
    if not (skill_dir / "SKILL.md").is_file():
        raise SystemExit(f"Not a skill directory: {skill_dir}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    archive = args.output_dir / f"coursera-source-capture-{version}.zip"
    if archive.exists():
        archive.unlink()

    paths = sorted(
        path
        for path in skill_dir.rglob("*")
        if path.is_file()
        and path.relative_to(skill_dir).parts[0] in ALLOWED_TOP_LEVEL
        and not any(part in SKIP_PARTS for part in path.parts)
        and path.suffix not in {".pyc", ".pyo"}
    )
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in paths:
            relative = Path(skill_dir.name) / path.relative_to(skill_dir)
            info = zipfile.ZipInfo(relative.as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o755 if path.suffix == ".py" else 0o644) << 16
            bundle.writestr(info, path.read_bytes())

    digest = sha256(archive)
    checksum = archive.with_suffix(archive.suffix + ".sha256")
    checksum.write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
    print(f"archive={archive}")
    print(f"sha256={digest}")
    print(f"files={len(paths)}")


if __name__ == "__main__":
    main()
