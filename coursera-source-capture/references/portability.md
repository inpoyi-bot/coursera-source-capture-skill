# Portability and failure handling

The bundled API route shapes passed the source workflow on a multi-module
Coursera on-demand course. They are implementation evidence, not a promise that
every Coursera product uses the same backend.

## Recheck on every new course

- Course slug resolves to exactly one current course.
- Requested module exists in the official module order.
- `onDemandCourseMaterials.v2` returns module, lesson, item, type, and explicit
  lock data.
- Lecture-video response exposes `subtitlesVtt.en`; English may be absent even
  when another language is available.
- Supplement and lecture-assets endpoints may return different asset types or
  no source.
- Some courses use `coach` and `ungradedLti` as well as widgets/plugins. Treat
  explicitly unlocked instances as interactive manual-queue items and capture
  static instructions/launch metadata only. Inventory any other unknown type;
  do not invent a capture method.

WebVTT cue IDs are optional and need not be numeric. The converter adds a
mechanical `cue_index` for validation while retaining the original cue ID.
Timestamps may use `MM:SS.mmm` or `HH:MM:SS.mmm`; both are accepted. Never
replace missing timestamps with estimates.

## Safe adaptation order

1. Save the exact error class/status and minimal response shape without
   credentials or transient URLs.
2. Determine whether the failure is course access, lock state, endpoint shape,
   subtitle-language absence, or a script defect.
3. Prefer a narrow parser/field adaptation in staging and rerun existing
   validators.
4. If public APIs lack content, use the already logged-in browser only within
   the widget/browser policy; never export auth state to make the API work.
5. If identity or lock state remains uncertain, set
   `needs_inventory_refresh` and stop capture for that item.

Do not downgrade validation, mark unknown as unlocked, accept non-WebVTT bytes,
or treat page-shell HTML as course content just to increase completion counts.

## Claims

Say “lecture/supplement complete” when those source classes pass independently.
Say “fully source-captured” only when the durable queue and module manifest have
no open eligible/unknown item. When access or platform variation prevents full
capture, report the exact remaining types and gap IDs rather than claiming the
skill supports them automatically.
