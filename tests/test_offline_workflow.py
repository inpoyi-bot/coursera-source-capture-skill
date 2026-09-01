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
            self.assertEqual(queue["schema_version"], 2)
            self.assertNotIn("course_slug", queue)
            self.assertEqual(queue["counts"]["total"], 2)
            self.assertEqual(queue["counts"]["known_unlocked"], 1)
            self.assertEqual(queue["counts"]["needs_inventory_refresh"], 1)
            self.assertEqual(queue["course_counts"]["synthetic-course"], queue["counts"])
            self.assertTrue(
                all(item["course_slug"] == "synthetic-course" for item in queue["items"])
            )
            lab = next(item for item in queue["items"] if item["item_id"] == "lab-1")
            self.assertTrue(
                any("do not fill or submit" in rule for rule in lab["verification_required"])
            )
            self.assertNotIn("lab-locked", {item["item_id"] for item in queue["items"]})

    def test_queue_supports_multiple_courses_without_identity_collision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pin(root)
            queue_json = root / "manual_capture_queue.json"
            queue_md = root / "manual_capture_queue.md"

            def inventory(course_slug: str, title: str) -> dict[str, object]:
                return {
                    "course_slug": course_slug,
                    "module_number": 1,
                    "items": [
                        {
                            "display_order": 1,
                            "title": title,
                            "coursera_item_id": "shared-item-id",
                            "slug": "shared-widget",
                            "type": "ungradedWidget",
                            "is_locked": False,
                            "url": (
                                f"https://www.coursera.org/learn/{course_slug}/"
                                "ungradedWidget/shared-item-id/shared-widget"
                            ),
                        }
                    ],
                }

            first_inventory = root / "first-module-items.json"
            second_inventory = root / "second-module-items.json"
            first_inventory.write_text(
                json.dumps(inventory("course-alpha", "Alpha widget")),
                encoding="utf-8",
            )
            second_inventory.write_text(
                json.dumps(inventory("course-beta", "Beta widget")),
                encoding="utf-8",
            )

            run_script(
                "sync_manual_capture_queue.py",
                first_inventory,
                queue_json,
                queue_md,
            )
            run_script(
                "sync_manual_capture_queue.py",
                second_inventory,
                queue_json,
                queue_md,
            )

            queue = json.loads(queue_json.read_text(encoding="utf-8"))
            self.assertEqual(queue["counts"]["total"], 2)
            self.assertEqual(set(queue["course_counts"]), {"course-alpha", "course-beta"})
            self.assertEqual(
                {item["course_slug"] for item in queue["items"]},
                {"course-alpha", "course-beta"},
            )
            self.assertEqual(
                len({item["gap_id"] for item in queue["items"]}),
                2,
            )

            first_inventory.write_text(
                json.dumps(inventory("course-alpha", "Updated Alpha widget")),
                encoding="utf-8",
            )
            run_script(
                "sync_manual_capture_queue.py",
                first_inventory,
                queue_json,
                queue_md,
            )
            updated = json.loads(queue_json.read_text(encoding="utf-8"))
            self.assertEqual(updated["counts"]["total"], 2)
            titles = {item["course_slug"]: item["title"] for item in updated["items"]}
            self.assertEqual(titles["course-alpha"], "Updated Alpha widget")
            self.assertEqual(titles["course-beta"], "Beta widget")
            self.assertIn("| Course | Gap ID |", queue_md.read_text(encoding="utf-8"))

    def test_queue_v1_migration_preserves_item_state_and_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pin(root)
            queue_json = root / "manual_capture_queue.json"
            queue_md = root / "manual_capture_queue.md"
            legacy = {
                "schema_version": 1,
                "last_updated": "2026-08-24",
                "policy": "capture_policy.md",
                "course_slug": "legacy-course",
                "completion_rule": "Synthetic completion rule.",
                "status_definitions": {},
                "counts": {
                    "total": 1,
                    "known_unlocked": 1,
                    "manual_capture_pending": 0,
                    "partial_capture": 1,
                    "needs_inventory_refresh": 0,
                    "captured_unverified": 0,
                    "verified": 0,
                    "blocked": 0,
                },
                "items": [
                    {
                        "gap_id": "LEGACY-STABLE-ID",
                        "module": 2,
                        "display_order": 4,
                        "item_id": "legacy-item",
                        "title": "Legacy widget",
                        "type": "ungradedWidget",
                        "slug": "legacy-widget",
                        "is_locked": False,
                        "eligibility": "eligible_unlocked",
                        "status": "partial_capture",
                        "source_url": "https://www.coursera.org/learn/legacy-course/ungradedWidget/legacy-item/legacy-widget",
                        "existing_sources": ["metadata"],
                        "missing_sources": ["body"],
                        "next_manual_action": "Capture the complete body.",
                        "expected_raw_dir": "raw/legacy-course/module-02/widgets/04-legacy-widget/",
                        "expected_readable_path": "readable/legacy-course/module-02/widgets/04-legacy-widget.md",
                        "verification_required": ["complete body preserved"],
                        "last_checked": "2026-08-24",
                    }
                ],
            }
            queue_json.write_text(json.dumps(legacy), encoding="utf-8")

            run_script(
                "sync_manual_capture_queue.py",
                "--migrate-only",
                queue_json,
                queue_md,
            )
            migrated = json.loads(queue_json.read_text(encoding="utf-8"))
            self.assertEqual(migrated["schema_version"], 2)
            self.assertNotIn("course_slug", migrated)
            self.assertEqual(migrated["items"][0]["course_slug"], "legacy-course")
            self.assertEqual(migrated["items"][0]["gap_id"], "LEGACY-STABLE-ID")
            self.assertEqual(migrated["items"][0]["status"], "partial_capture")
            self.assertEqual(migrated["items"][0]["last_checked"], "2026-08-24")
            self.assertEqual(migrated["course_counts"]["legacy-course"], migrated["counts"])

            before_second_run = migrated["items"]
            run_script(
                "sync_manual_capture_queue.py",
                "--migrate-only",
                queue_json,
                queue_md,
            )
            after_second_run = json.loads(queue_json.read_text(encoding="utf-8"))
            self.assertEqual(after_second_run["items"], before_second_run)

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
