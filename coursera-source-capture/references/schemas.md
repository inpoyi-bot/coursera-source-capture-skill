# Project and provenance schemas

## Directory contract

```text
PROJECT_ROOT/
  .coursera-source-capture-root.json
  README.md
  capture_policy.md
  manual_capture_queue.json
  manual_capture_queue.md
  raw/COURSE_SLUG/module-XX/
    transcripts/
    slides/
    readings/
    videos/
    widgets/
    lesson_index.json
    module_items.json
    capture_manifest.md
  readable/COURSE_SLUG/module-XX/
    transcripts/
    widgets/
  readable/COURSE_SLUG/readable_manifest.json
```

Empty contract directories are allowed. Do not place captured files outside the
authoritative project root.

The root marker contains only schema, project type, active status, creation time,
and purpose. It deliberately does not store an absolute path, so an intentional
project move remains portable. Bundled writers resolve the marker's current
parent and fail closed when no active marker exists. Archive/mirror directories
must not retain an active marker and must say so in their README.

## Module inventory invariants

Each `module_items.json` entry retains:

- `display_order`, `section`, `title`;
- `coursera_item_id`, `slug`, `type`, `url`;
- `is_locked`: exactly `true`, `false`, or `null`;
- time commitment when the API exposes it.

`null` means unknown, not unlocked. Preserve official item type names because
they determine URL routing and capture policy.

Each lecture record additionally retains lecture order and file stem. Lecture
order is independent of module display order.

## Multi-course queue

`manual_capture_queue.json` uses schema version 2. It is shared by every course
under one active project root. The top level contains global `counts`,
`course_counts` keyed by course slug, and `items`. It does not contain a single
top-level `course_slug`; every item carries its own course identity.

Before adding another course to a root with a schema-v1 queue, run:

```text
python3 -B scripts/sync_manual_capture_queue.py --migrate-only QUEUE_JSON QUEUE_MD
```

Migration preserves existing gap IDs, statuses, evidence, verification fields,
and `last_checked` values. It adds each legacy top-level course slug to its
items, removes the single-course field, recomputes global and per-course counts,
and rerenders the Markdown register.

## Queue entry

Use a stable ID derived from course slug, module, and item ID. If item ID is
unknown, use module/display order and never silently replace the ID later;
reconcile the existing entry.

Required fields:

- gap ID, course slug, module, display order;
- item ID, title, type, slug, explicit lock state;
- stable source URL;
- eligibility and status;
- existing and missing sources;
- next manual action and retry condition;
- expected raw directory and readable path;
- verification requirements and last checked date.

Statuses:

- `needs_inventory_refresh`: identity or current lock state is unresolved;
- `manual_capture_pending`: explicitly unlocked and not yet attempted;
- `partial_capture`: metadata/provenance exists but required body is incomplete;
- `captured_unverified`: files exist but completeness or hashes are unverified;
- `verified`: required sources, completeness, provenance, and hashes passed;
- `blocked`: an attempted capture cannot proceed and has a concrete retry
  condition.

Keep verified entries as audit history. Recompute counts from entries; never
hand-maintain stale totals. Match and sort items using course slug as part of
their identity; module numbers and Coursera item IDs are not globally unique
across courses.

## Per-file provenance

For each raw source record:

- stable source page or official API class;
- capture time with timezone;
- relative local path, bytes, SHA-256;
- capture method and whether the source is raw or derived;
- attachment/API check result;
- missing source or failure detail when incomplete.

Never persist download query strings or temporary signed URLs. A stable Coursera
lesson URL is appropriate provenance; the transient subtitle/asset URL is not.

## Readable derivative

Readable Markdown retains lecture title, section, lecture order, source VTT
filename, and source SHA-256. Paragraphs group consecutive cues into roughly
20–40-second spans and retain `[start–end]`. The concatenated cue wording before
and after grouping must be exactly equal.
