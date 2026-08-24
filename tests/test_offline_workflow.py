from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = REPO_ROOT / "coursera-source-capture"
SCRIPTS = SKILL_DIR / "scripts"
MARKER = {
    "schema_version": 1,
    "project_type": "coursera-source-capture",
    "status": "active",
    "purpose": "synthetic test root",
}


def run_script(name: str, *args: object, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment["PYTHONPYCACHEPREFIX"] = str(Path(tempfile.gettempdir()) / "coursera-skill-tests-pycache")
    return subprocess.run(
        [sys.executable, "-B", str(SCRIPTS / name), *(str(value) for value in args)],
        cwd=cwd or REPO_ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=True,
    )


def pin(root: Path) -> None:
    (root / ".coursera-source-capture-root.json").write_text(
        json.dumps(MARKER), encoding="utf-8"
    )


class OfflineWorkflowTests(unittest.TestCase):
    def test_all_scripts_expose_help_without_network(self) -> None:
        for script in sorted(SCRIPTS.glob("*.py")):
            if script.name == "capture_paths.py":
                continue
            with self.subTest(script=script.name):
                result = run_script(script.name, "--help")
                self.assertIn("usage:", result.stdout)

    def test_vtt_conversion_validation_and_readable_render(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pin(root)
            transcripts = root / "raw" / "course" / "module-01" / "transcripts"
            transcripts.mkdir(parents=True)
            vtt = transcripts / "01-synthetic.en.vtt"
            vtt.write_text(
                "WEBVTT\n\n"
                "cue-a\n00:00.000 --> 00:02.000\nSynthetic first sentence.\n\n"
                "00:02.000 --> 00:04.000\nSynthetic second sentence.\n",
                encoding="utf-8",
            )
            lesson = {
                "schema_version": 1,
                "course_slug": "synthetic-course",
                "module_number": 1,
                "video_lectures": [
                    {
                        "order": 1,
                        "section": "Synthetic section",
                        "title": "Synthetic lecture",
                        "coursera_item_id": "item-1",
                        "display_order": 1,
                        "is_locked": False,
                        "duration_displayed": "1 min",
                        "url": "https://www.coursera.org/learn/synthetic-course/lecture/item-1/synthetic",
                        "file_stem": "01-synthetic",
                    }
                ],
            }
            lesson_index = transcripts.parent / "lesson_index.json"
            lesson_index.write_text(json.dumps(lesson), encoding="utf-8")

            run_script("vtt_to_markdown.py", transcripts, lesson_index)
            validation = run_script("validate_coursera_transcripts.py", transcripts, lesson_index)
            self.assertIn("validated=1", validation.stdout)

            readable = root / "readable" / "course"
            render = run_script(
                "render_readable_transcript.py",
                root / "raw" / "course",
                readable,
            )
            self.assertIn("complete lessons=1", render.stdout)
            output = readable / "module-01" / "transcripts" / "01-synthetic.en.readable.md"
            text = output.read_text(encoding="utf-8")
            self.assertIn("Synthetic first sentence. Synthetic second sentence.", text)

    def test_queue_skips_locked_and_recognizes_lab_case_insensitively(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pin(root)
            inventory = {
                "course_slug": "synthetic-course",
                "module_number": 1,
                "items": [
                    {
                        "display_order": 1,
                        "title": "Hands-On Lab: Synthetic",
                        "coursera_item_id": "lab-1",
                        "slug": "synthetic-lab",
                        "type": "ungradedWidget",
                        "is_locked": False,
                        "url": "https://www.coursera.org/learn/synthetic-course/ungradedWidget/lab-1/synthetic-lab",
                    },
                    {
                        "display_order": 2,
                        "title": "Unknown glossary",
                        "coursera_item_id": "glossary-1",
                        "slug": "unknown-glossary",
                        "type": "ungradedPlugin",
                        "is_locked": None,
                        "url": "https://www.coursera.org/learn/synthetic-course/ungradedPlugin/glossary-1/unknown-glossary",
                    },
                    {
                        "display_order": 3,
                        "title": "Locked lab",
                        "coursera_item_id": "lab-locked",
                        "slug": "locked-lab",
                        "type": "ungradedWidget",
                        "is_locked": True,
                        "url": "https://www.coursera.org/learn/synthetic-course/ungradedWidget/lab-locked/locked-lab",
                    },
                ],
            }
            module_items = root / "module_items.json"
            queue_json = root / "manual_capture_queue.json"
            queue_md = root / "manual_capture_queue.md"
            module_items.write_text(json.dumps(inventory), encoding="utf-8")
            run_script("sync_manual_capture_queue.py", module_items, queue_json, queue_md)

            queue = json.loads(queue_json.read_text(encoding="utf-8"))
            self.assertEqual(queue["counts"]["total"], 2)
            self.assertEqual(queue["counts"]["known_unlocked"], 1)
            self.assertEqual(queue["counts"]["needs_inventory_refresh"], 1)
            lab = next(item for item in queue["items"] if item["item_id"] == "lab-1")
            self.assertTrue(
                any("do not fill or submit" in rule for rule in lab["verification_required"])
            )
            self.assertNotIn("lab-locked", {item["item_id"] for item in queue["items"]})

    def test_archive_and_unpinned_roots_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inventory = root / "module_items.json"
            inventory.write_text(
                json.dumps(
                    {
                        "course_slug": "synthetic-course",
                        "module_number": 1,
                        "items": [],
                    }
                ),
                encoding="utf-8",
            )
            command = [
                sys.executable,
                "-B",
                str(SCRIPTS / "sync_manual_capture_queue.py"),
                str(inventory),
                str(root / "manual_capture_queue.json"),
                str(root / "manual_capture_queue.md"),
            ]
            unpinned = subprocess.run(command, text=True, capture_output=True)
            self.assertNotEqual(unpinned.returncode, 0)
            self.assertIn("No active", unpinned.stderr)

            pin(root)
            (root / "README.md").write_text(
                "# Merged archive\n\nDo not continue capture here.\n",
                encoding="utf-8",
            )
            archived = subprocess.run(command, text=True, capture_output=True)
            self.assertNotEqual(archived.returncode, 0)
            self.assertIn("archive/mirror", archived.stderr)


if __name__ == "__main__":
    unittest.main()
