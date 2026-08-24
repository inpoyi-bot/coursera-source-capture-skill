# Widget and plugin capture

Apply this to a widget, plugin, LTI, coach, glossary, or lab only when its
current inventory says `is_locked:false` and
whose durable queue entry already exists.

## Source priority and stopping rule

1. Official original attachment.
2. Official API body.
3. Iframe/source package/raw HTML.
4. Complete browser-rendered PDF fallback plus visible/mechanical text.
5. Complete user-pasted visible text with explicit completeness attestation and
   capture of every page link.
6. Screenshot as auxiliary evidence only.

Use `scripts/capture_coursera_widget_metadata.py` to preserve the exact official
course-materials item object when available. This proves identity and lock
state, not body completeness.

Start with one representative static reading or glossary. Do not begin with a
lab unless no static item exists. If the sample cannot produce a complete body
and attachment check, record `partial_capture` or `blocked`, update both queue
files and the module manifest, and stop broader widget automation.

## Logged-in Chrome

When the user requests or permits their existing Chrome session, use the Chrome
control skill and obey its tab ownership rules. Prefer a new task-owned tab or
an explicitly released matching Coursera tab. If another Codex task controls
the needed tab, stop browser work and identify the tab instead of repeatedly
claiming or navigating user tabs.

Use cheap checks first: page title/URL, visible DOM or a viewport screenshot,
then targeted iframe/src/link inspection. Do not start with a full DOM snapshot
across several pages. Inspect observed page assets only after reading that
capability's documentation. Never read cookies, local storage, browser profiles,
or authentication/session artifacts.

Do not treat a generic Coursera application shell as the content body. If page
reads time out, record each bounded attempt, what was actually observed, and the
retry condition; do not keep escalating timeouts or switch to credential export.

## Known Chrome page-control failure mode

Treat the following combination as the local known limitation
`KL-CHROME-COURSERA-WIDGET-001`, especially on Coursera `ungradedWidget` pages:

- Chrome and the extension/native host are running, and tabs or title/URL
  metadata can be listed;
- a matching tab remains owned by an idle or previous Codex task, an exact claim
  is rejected, or a new task-owned tab can be created but page navigation stalls;
- title/URL may succeed while the next DOM, screenshot, iframe, or link read times
  out or resets the browser connection.

This signature establishes a per-task/per-tab page-control failure, not missing
course content. It does not by itself prove whether the upstream cause is Codex,
Chrome, Coursera's SPA/widget lifecycle, or their interaction. Do not recommend
reinstalling the extension when installation diagnostics and tab listing pass.
Do not describe a tab as released merely because a task stopped; release is
established only when the browser capability no longer reports conflicting
ownership or the new task successfully claims the exact tab.

Use this failure budget:

1. If another task owns the exact tab, stop and identify its title/URL and owning
   task/session. Let the user end or release that control before one fresh claim.
2. Prefer one manually preloaded matching tab. After ownership is resolved, use
   one cheap title/URL check followed by one lightweight page-body check: visible
   DOM or a viewport screenshot.
3. If that page-body check times out or resets, stop browser automation for the
   item. Do not repeat `goto`, increase timeouts, create more tasks, or cycle
   through additional user tabs.
4. Preserve the exact attempt and observed boundary in the item manifest, then
   use the manual evidence bundle below.

Record this limitation once in the project's durable policy or known-limitations
record and link affected item manifests to it. Retest after a Chrome/plugin
version change, on a different Coursera course, or in a controlled fresh-tab
reproduction; do not promote it to a generic upstream product bug without that
evidence.

## Browser-rendered PDF fallback

Use only after recording why higher-priority sources failed and confirming no
official attachment is available. The print preview must contain the complete
body, including below-fold sections. Record it as `browser-rendered`, with stable
page URL, capture time, bytes, and SHA-256. Never call it an official PDF.

Mechanically extract readable Markdown only when the PDF/text completeness can
be verified. Do not use OCR or screenshots to reconstruct missing content.

## Manual evidence bundle

Use this fallback after the Chrome failure budget is exhausted or when a complete
browser-rendered PDF is unavailable:

1. Preserve the official course-materials item object and reconfirm
   `is_locked:false` immediately before accepting the capture.
2. Ask the user to copy the complete visible body from first line to last line,
   retaining every download/support link. This requests course text, never a
   password, cookie, token, session export, or learner answer.
3. Save the untouched input as a clearly labelled raw source such as
   `page-visible-text.user-pasted.txt`. Do not call it official HTML, API output,
   or an official attachment.
4. Match item identity using stable URL/item ID plus distinctive title, scenario,
   section, or task-structure markers. Record the basis; do not silently infer a
   match from generic Coursera chrome.
5. Obtain an explicit user confirmation that the copy spans the page's first
   line through last line and includes every download link. Record the
   attestation and its scope. It proves visible-body/link completeness, not
   publisher-authenticated HTML.
6. Download each stable, non-signed page-linked source file without a logged-in
   cookie when possible. Preserve originals, record the source URL, bytes, and
   SHA-256, and validate real file/package type rather than trusting extensions.
7. Produce readable Markdown mechanically. Prefer byte-for-byte identity with
   the pasted text; if formatting is changed, prove full text preservation and
   register both hashes.
8. Verify the manifest, queue JSON/Markdown, missing-source list, and security
   facts before changing the item status.

The item may advance to `verified` with verification basis
`user_attested_visible_text` only when all of these are true:

- the current lock state is explicitly `false`;
- identity and complete first-to-last-line body coverage are established;
- every visible page link was captured or explicitly checked and accounted for;
- source bytes/hashes and attachment/package integrity pass;
- readable output is a proven mechanical derivative;
- provenance explicitly says `user-pasted`, with no official-source inflation;
- `missing_sources` is empty and no lab launch, answer entry, upload, submission,
  credential/session capture, or learner-progress change occurred.

Keep verification basis separate from completion status. Prefer these evidence
classes in manifests:

- `authoritative_source`: official attachment, API body, iframe/source package,
  or raw HTML;
- `browser_rendered`: complete browser-rendered PDF/DOM with visual or structural
  completeness verification;
- `user_attested_visible_text`: complete user-pasted body and links satisfying
  the gate above.

If any gate is missing, retain `captured_unverified`, `partial_capture`, or
`blocked` with the exact missing evidence and retry condition. A user paste alone
does not make an item verified.

## Hands-on labs

Capture only:

- page instructions and static task steps;
- task/input structure without personal entries;
- iframe or external-tool entry metadata;
- launch/config JSON that contains no credential;
- official downloadable assets.

Never type answers, initialize or submit work, start a coach conversation, mark the lab complete, or save
personal input/progress. If the launch itself changes progress, stop before it
and record the limitation.

## Item source manifest

Record title, module/display order, item ID/type/slug, explicit lock state,
stable URL, captured sources/hashes, source-priority checks, browser/API attempts,
missing sources, capture status, retry condition, and explicit security facts:
no password, cookie/session export, token, signed URL, or personal learning state.
