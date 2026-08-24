from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", ".venv", "dist", "__pycache__"}
FORBIDDEN_OUTPUT_NAMES = {
    ".coursera-source-capture-root.json",
    "manual_capture_queue.json",
    "manual_capture_queue.md",
    "module_items.json",
    "lesson_index.json",
    "official-item-api.json",
    "source_manifest.json",
    "capture_manifest.md",
}


class RepositorySafetyTests(unittest.TestCase):
    def test_repository_is_not_a_capture_root(self) -> None:
        self.assertFalse((REPO_ROOT / ".coursera-source-capture-root.json").exists())
        self.assertFalse(
            (REPO_ROOT / "coursera-source-capture" / ".coursera-source-capture-root.json").exists()
        )

    def test_no_course_output_contract_is_present(self) -> None:
        forbidden = [
            REPO_ROOT / "raw",
            REPO_ROOT / "readable",
            REPO_ROOT / "manual_capture_queue.json",
            REPO_ROOT / "manual_capture_queue.md",
            REPO_ROOT / "capture_policy.md",
            REPO_ROOT / "capture_manifest.md",
            REPO_ROOT / "coursera-source-capture" / "raw",
            REPO_ROOT / "coursera-source-capture" / "readable",
        ]
        present = [path for path in forbidden if path.exists()]
        self.assertEqual(present, [], f"Local capture output entered repo: {present}")

    def test_no_capture_artifacts_anywhere_in_trackable_tree(self) -> None:
        violations: list[Path] = []
        for path in REPO_ROOT.rglob("*"):
            relative = path.relative_to(REPO_ROOT)
            if any(part in SKIP_DIRS for part in relative.parts):
                continue
            if path.is_dir() and path.name in {"raw", "readable"}:
                violations.append(relative)
            if not path.is_file():
                continue
            if path.name in FORBIDDEN_OUTPUT_NAMES:
                violations.append(relative)
            if path.suffix.lower() in {".vtt", ".cml"}:
                violations.append(relative)
            if path.name.endswith((".supplement.json", ".en.json", ".en.md")):
                violations.append(relative)
        self.assertEqual(violations, [], f"Capture artifacts entered repo: {violations}")

    def test_gitignore_contains_output_guards(self) -> None:
        rules = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        required = {
            "/.coursera-source-capture-root.json",
            "/raw/",
            "/readable/",
            "/manual_capture_queue.json",
            "/manual_capture_queue.md",
            "/coursera-source-capture/raw/",
            "/coursera-source-capture/readable/",
        }
        self.assertTrue(required.issubset(set(rules)))


if __name__ == "__main__":
    unittest.main()
