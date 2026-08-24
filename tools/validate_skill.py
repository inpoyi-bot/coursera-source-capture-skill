#!/usr/bin/env python3
"""Validate the public Coursera source-capture skill without network access."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import yaml


ALLOWED_FRONTMATTER = {"name", "description", "license", "allowed-tools", "metadata"}
SECRET_MARKERS = (
    "-----BEGIN PRIVATE KEY-----",
    "ghp_",
    "github_pat_",
    "AKIA",
)


def frontmatter(content: str) -> tuple[dict[str, object], str]:
    match = re.match(r"^---\n(.*?)\n---(?:\n|$)", content, re.DOTALL)
    if not match:
        raise ValueError("SKILL.md has invalid or missing YAML frontmatter")
    payload = yaml.safe_load(match.group(1))
    if not isinstance(payload, dict):
        raise ValueError("SKILL.md frontmatter must be a mapping")
    return payload, content[match.end() :]


def validate(skill_dir: Path) -> None:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        raise ValueError(f"Missing {skill_md}")
    content = skill_md.read_text(encoding="utf-8")
    metadata, body = frontmatter(content)

    unexpected = set(metadata) - ALLOWED_FRONTMATTER
    if unexpected:
        raise ValueError(f"Unexpected frontmatter keys: {sorted(unexpected)}")
    name = metadata.get("name")
    description = metadata.get("description")
    if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
        raise ValueError("Skill name must be non-empty hyphen-case")
    if name != skill_dir.name:
        raise ValueError(f"Skill name {name!r} does not match directory {skill_dir.name!r}")
    if len(name) > 64:
        raise ValueError("Skill name exceeds 64 characters")
    if not isinstance(description, str) or not description.strip():
        raise ValueError("Skill description must be a non-empty string")
    if len(description) > 1024 or "<" in description or ">" in description:
        raise ValueError("Skill description has invalid length or angle brackets")
    if re.search(r"^ {0,3}\[TODO:[^\n]*\]\s*$", body, re.MULTILINE):
        raise ValueError("Skill contains an unfinished TODO placeholder")

    for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", content):
        if target.startswith(("http://", "https://", "#")):
            continue
        reference = (skill_dir / target).resolve()
        if not reference.is_file():
            raise ValueError(f"Broken SKILL.md reference: {target}")

    agent_file = skill_dir / "agents" / "openai.yaml"
    if agent_file.is_file():
        agent_data = yaml.safe_load(agent_file.read_text(encoding="utf-8"))
        if not isinstance(agent_data, dict) or not isinstance(agent_data.get("interface"), dict):
            raise ValueError("agents/openai.yaml must contain an interface mapping")

    text_files = [
        path
        for path in skill_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in {".md", ".py", ".yaml", ".yml"}
    ]
    for path in text_files:
        text = path.read_text(encoding="utf-8")
        personal_path = "/Users/" in text or re.search(
            r"(?:^|[\"'= (])/home/[A-Za-z0-9._-]+/",
            text,
            re.MULTILINE,
        )
        if personal_path:
            raise ValueError(f"Personal absolute path found in {path}")
        for marker in SECRET_MARKERS:
            if marker in text:
                raise ValueError(f"Possible secret marker {marker!r} found in {path}")
        if path.suffix == ".py":
            compile(text, str(path), "exec")

    print(f"Skill is valid: {skill_dir}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("skill_dir", type=Path)
    args = parser.parse_args()
    validate(args.skill_dir.resolve())


if __name__ == "__main__":
    main()
