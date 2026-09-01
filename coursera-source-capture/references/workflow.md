# Capture workflow

Use this sequence for one course module. Keep API/browser observations separate
from inferred state.

## 1. Preflight

1. Resolve the authoritative project root and course slug.
2. For a new empty root, pin it before any other write:

   ```text
   python3 -B scripts/init_capture_project.py PROJECT_ROOT
   ```

   For a verified existing project that has `capture_policy.md`, `raw/`, and
   `readable/` but no marker, use `--adopt-existing`. Never adopt a directory
   whose README identifies it as an archive, mirror, merge source, or says not
   to continue capture there.
3. Record and report the absolute root printed by the initializer. Treat the
   marker's parent as `PROJECT_ROOT` for the whole run. Every bundled writer
   refuses output outside that active marker tree.
4. Read current policy, queue, prior manifests, and actual raw/readable files.
   If a shared root still has a schema-v1 single-course queue, migrate it before
   inventorying a second course:

   ```text
   python3 -B scripts/sync_manual_capture_queue.py --migrate-only QUEUE_JSON QUEUE_MD
   ```

5. Record before-state queue counts and hashes or modification times for modules
   that must remain untouched.
6. Work in a new staging directory under `PROJECT_ROOT`. Do not create the target module over an
   existing directory.

The skill installation directory and Git repository are code locations, never
capture-output roots. Do not fall back to the shell working directory when the
authoritative root is absent or ambiguous; stop before writing.

## 2. Official inventory

Run:

```text
python3 -B scripts/build_coursera_module_index.py COURSE_SLUG MODULE_NUMBER STAGING_MODULE_DIR
```

Verify `module_items.json` against the official order. It must retain module,
section, display order, title, item ID, type, slug, stable URL, and the exact
boolean/null lock state. `lesson_index.json` retains every lecture, including
locked/unknown lecture records, so capture scripts can explicitly skip them.

Report counts by type and lock state before capture. Do not infer `false` from a
missing lock field. If the public course-materials API cannot establish current
state, use the logged-in course outline for inventory only; mark unresolved
items `needs_inventory_refresh`.

## 3. Durable widget/plugin queue

Before opening any unlocked widget/plugin/LTI/coach item, run:

```text
python3 -B scripts/sync_manual_capture_queue.py MODULE_ITEMS_JSON QUEUE_JSON QUEUE_MD
```

The script adds explicitly unlocked items as `manual_capture_pending`, unknown
items as `needs_inventory_refresh`, keeps completed audit entries, and
recomputes global and per-course counts. Schema-v2 matching includes course
slug, module, and item identity so separate courses cannot overwrite one
another. Locked items stay in the module manifest and are not added as eligible
capture work.

## 4. Lectures

Run the capture, conversion, and validator against staging:

```text
python3 -B scripts/capture_coursera_public_vtt.py LESSON_INDEX TRANSCRIPTS_DIR
python3 -B scripts/vtt_to_markdown.py TRANSCRIPTS_DIR LESSON_INDEX
python3 -B scripts/validate_coursera_transcripts.py TRANSCRIPTS_DIR LESSON_INDEX
```

The VTT downloader uses the official lecture-video API and only captures
lectures with `is_locked:false`. Subtitle download URLs are inbound-only and
must not appear in indexes or manifests.

Acceptance checks:

- one VTT, cue JSON, and raw Markdown per unlocked lecture;
- official order, title, item ID, section, and stable URL match inventory;
- VTT begins with `WEBVTT`; no truncation marker;
- mechanical cue indices are sequential; original cue IDs remain unmodified;
- timestamps are parseable, ranges valid, and starts monotonic;
- JSON source hash equals the raw VTT hash.

## 5. Readings and official files

Run:

```text
python3 -B scripts/capture_coursera_public_readings.py LESSON_INDEX READINGS_DIR
python3 -B scripts/inspect_coursera_public_assets.py LESSON_INDEX ASSET_STAGING_DIR
```

Preserve raw supplement API bytes, CML, renderable metadata, and eligible
original attachments. Move downloaded slide/notes files and their inventory
into the module `slides/` contract only after validating hashes. Record
`none exposed` only after the relevant endpoint was checked; otherwise use
`not checked`.

## 6. Readable transcript layer

Run the renderer against a staging source tree whose structure is
`module-XX/transcripts/*.en.json`:

```text
python3 -B scripts/render_readable_transcript.py RAW_COURSE_ROOT READABLE_STAGING_ROOT
```

For an existing course, compare regenerated earlier modules byte-for-byte and
install only the new module plus the updated `readable_manifest.json`. Verify
every readable file equals a fresh deterministic render of its cue JSON and
that the manifest records source VTT hashes, cue count, paragraph count, and
text-preservation success.

## 7. Widgets, plugins, glossaries, and labs

Follow [widget-capture.md](widget-capture.md). Update both queue files and the
module manifest after every attempt. Do not proceed to a batch after the
representative sample fails.

## 8. Manifest and final gate

The module manifest must enumerate every official item, including locked items,
and every captured file with relative path, bytes, SHA-256, source class, and
provenance. It must distinguish `checked; none exposed` from `not checked` and
state every open gap ID.

Rerun the transcript validator on installed files, audit readable equivalence,
recompute queue counts from entries, verify JSON/Markdown queue agreement, scan
for persisted credentials/signed URLs, and verify earlier modules were not
modified. Report lecture/supplement completion separately from full module
source-capture completion.
