# Changelog

All notable changes are documented here. The project follows Semantic
Versioning.

## Unreleased

### Added

- active project-root marker, archive detection, and fail-closed output-path
  enforcement across all bundled writers.
- repository-level output exclusions and regression checks preventing captured
  course material from entering source control or release archives.
- schema-v2 manual queue support for multiple courses in one active project
  root, including global and per-course counts.
- `--migrate-only` conversion from schema-v1 queues that preserves gap IDs,
  statuses, verification evidence, and historical item check dates.

### Fixed

- include course slug in queue matching and sorting keys so identical module or
  item IDs from different courses cannot overwrite each other.

## 0.1.0 - 2026-08-24

### Added

- provenance-preserving Coursera module and lesson inventory;
- English WebVTT capture and deterministic timestamped Markdown conversion;
- readable transcript rendering with text-preservation verification;
- reading and first-party attachment inspection;
- durable manual queue for widgets, plugins, glossaries, LTI items, coaches,
  and labs;
- bounded Chrome page-control failure handling;
- `user_attested_visible_text` manual evidence fallback with strict verification
  gates;
- offline regression tests, skill validation, deterministic packaging, and
  GitHub Actions workflows.

### Fixed

- recognize Hands-On Lab titles case-insensitively when adding lab-specific
  verification requirements.
