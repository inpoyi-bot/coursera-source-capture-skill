---
name: coursera-source-capture
description: Capture accessible Coursera course modules as provenance-preserving raw sources and mechanically derived transcripts. Use for Coursera course inventory, English VTT capture, readings and official attachments, readable transcript generation, widget/glossary/lab source capture, durable gap queues, or source-completeness validation. Do not use for summaries, study notes, translation, quiz answers, or submitting coursework.
---

# Coursera Source Capture

Preserve Coursera material the learner is already entitled to access. Produce
raw evidence plus mechanical derivatives; do not perform knowledge processing.

## Start from current evidence

If an existing capture project is supplied, read its README, capture policy,
manual queue, target module manifest, and actual raw files before acting. Actual
files and current API/page evidence outrank old handoffs or previous claims.

For a new project, create the directory and provenance contract in
[references/schemas.md](references/schemas.md). Never write into a convenient
empty workspace when the user provided an authoritative project root.

Before any capture write, pin or verify the authoritative output root with
`scripts/init_capture_project.py`. Every bundled writer must resolve an active
`.coursera-source-capture-root.json` above its output path and refuse paths under
an unpinned directory or an archive/mirror. Report the resolved absolute root
before capture. Never use this skill directory, its Git repository, or the
current working directory as output merely because it is convenient.

Before capture, read [references/workflow.md](references/workflow.md). Read
[references/widget-capture.md](references/widget-capture.md) only when the
inventory contains widgets/plugins/glossaries/labs or a browser fallback is
needed. Read [references/portability.md](references/portability.md) when applying
the pipeline to a new course, when an API shape differs, or when a script fails.

Coursera `ungradedWidget` pages have a known local failure mode in which Chrome
tab metadata remains visible while claim, navigation, DOM, or screenshot reads
time out or reset. When those symptoms appear, follow the bounded retry and
manual evidence procedure in [references/widget-capture.md](references/widget-capture.md).
Do not diagnose an extension installation failure or keep retrying across Codex
tasks merely because the page body could not be read.

## Non-negotiable boundaries

- Never request or save passwords, cookies, CAUTH, tokens, browser profiles,
  session files, or temporary signed URLs.
- Prefer cookie-free official APIs. Use the learner's existing logged-in Chrome
  only for content that public APIs do not expose.
- Capture only items whose current lock state is explicitly `false`. Treat a
  missing or non-boolean lock state as unknown; inventory it and stop capture.
- Do not answer, fill, submit, or mark complete any quiz, assignment, lab,
  discussion, or graded item. For labs, preserve instructions, task structure,
  and official assets only.
- Preserve raw VTT and official attachments byte-for-byte. Never reconstruct
  slides from video frames when official files might exist.
- Mechanical JSON/Markdown may parse cues, collapse line breaks, and group cues
  into timestamped paragraphs. It must not summarize, translate, correct,
  normalize wording, or invent timestamps.
- Stage new files, validate them, then install them. Bundled scripts refuse to
  overwrite existing outputs; do not bypass that guard without explicit user
  direction and a verified backup/diff.

## Source and completion discipline

Use this priority: official original attachment; official API body; iframe or
source package/raw HTML; complete browser-rendered PDF fallback; complete
user-pasted visible text with explicit completeness attestation and full link
capture; screenshot as auxiliary evidence only. A browser-rendered PDF is never
an official PDF, and user-pasted text is never an official HTML/API source.

Register every explicitly unlocked widget/plugin/LTI/coach item in the durable manual queue
before attempting it. Use one representative static item first. If it fails,
record `partial_capture` or `blocked` with the exact retry condition and do not
scale the failing method across the module.

Do not call a module fully source-captured while any target item is
`needs_inventory_refresh`, `manual_capture_pending`, `partial_capture`,
`captured_unverified`, or `blocked`. Transcript completion is not module
completion.

## Bundled scripts

Resolve this skill's directory and run scripts from its `scripts/` folder. The
validated path is:

1. `init_capture_project.py`
2. `build_coursera_module_index.py`
3. `sync_manual_capture_queue.py`
4. `capture_coursera_public_vtt.py`
5. `vtt_to_markdown.py`
6. `validate_coursera_transcripts.py`
7. `capture_coursera_public_readings.py`
8. `inspect_coursera_public_assets.py`
9. `render_readable_transcript.py`

Use `capture_coursera_widget_metadata.py` only for explicitly unlocked
widget/plugin/LTI/coach metadata; metadata alone is a partial capture, never a
captured body. Do not start coach conversations or transmit learner input.

Run network-dependent scripts only with the user's authorized network access.
If the API fails, record the endpoint class, status/error, and item affected;
do not immediately rewrite the pipeline or weaken lock checks.
