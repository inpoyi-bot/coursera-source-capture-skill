# Coursera Source Capture Skill

A Codex skill for capturing Coursera course sources that a learner is already
authorized to access. It preserves raw evidence, provenance, lock state,
official attachments, English WebVTT transcripts, and mechanically derived
Markdown without generating summaries or study notes.

This is an independent community project. It is not affiliated with or endorsed
by Coursera or OpenAI.

## What it does

- inventories modules and preserves official lesson order, titles, item IDs,
  types, and explicit lock state;
- downloads English WebVTT exposed by first-party Coursera endpoints without
  exporting browser credentials;
- captures readings and eligible original slide/note attachments;
- converts VTT into timestamped raw Markdown and a more readable mechanical
  derivative while verifying text preservation;
- registers unlocked widgets, glossaries, plugins, and labs in a durable gap
  queue;
- applies bounded Chrome fallback rules and an auditable manual evidence bundle
  when Coursera widget pages cannot be read reliably;
- validates hashes, provenance, queue state, and source completeness.
- pins one authoritative output root with an active marker and makes bundled
  writers fail closed outside that tree or inside an archive/mirror.

It deliberately does **not** summarize, translate, answer quizzes, submit labs,
reconstruct slides from video frames, bypass access controls, or request/save
passwords, cookies, CAUTH, tokens, browser profiles, or signed download URLs.

## Requirements

- Codex with skills support
- Python 3.11 or newer
- `requests` 2.x for the network-assisted scripts
- Optional: Codex Chrome control for content unavailable from cookie-free
  first-party endpoints

Coursera's web API shapes are undocumented and may change. The skill treats
endpoint behavior as implementation evidence, not a compatibility guarantee.

## Install

Ask Codex to install the skill from the repository subdirectory:

```text
Use $skill-installer to install the skill from
https://github.com/inpoyi-bot/coursera-source-capture-skill/tree/main/coursera-source-capture
```

Or clone the repository and copy or symlink `coursera-source-capture/` into your
Codex skills directory, normally `~/.codex/skills/`.

Install the Python dependency when you intend to run the bundled network scripts:

```bash
python3 -m pip install -r requirements.txt
```

## Use

An explicit invocation is useful for a new capture project:

```text
Use $coursera-source-capture to inventory one accessible Coursera module,
capture raw English transcripts and official attachments, preserve provenance,
and generate only mechanical readable Markdown. Do not summarize or submit
coursework.
```

The skill will route to its detailed workflow and widget fallback references as
needed. Start with one representative module or static widget before scaling.

## Output-root safety

Course material is never written into this Git repository or the installed
skill directory. Before capture, initialize a new root:

```bash
python3 coursera-source-capture/scripts/init_capture_project.py /absolute/path/to/PROJECT_ROOT
```

For a verified existing capture project, add `--adopt-existing`. Adoption fails
unless the expected capture contract exists, and it refuses README files that
identify the directory as an archive, mirror, or non-execution copy.

The initializer writes `.coursera-source-capture-root.json`. Every bundled
writer resolves that marker before any network request or file write and prints
the resolved absolute root. The marker stores no absolute path, so an intentional
project move remains portable.

Captured outputs remain local. The repository `.gitignore` excludes root
markers, `raw/`, `readable/`, queues, manifests, and common capture-output
directories as defense in depth. Releases package only the installable skill
folder; they never package a capture project.

## Output contract

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
```

See [`coursera-source-capture/references/schemas.md`](coursera-source-capture/references/schemas.md)
for the complete provenance contract.

## Safety and lawful use

Use this project only for material you are legally entitled to access and only
in ways permitted by applicable law and platform terms. Do not use it to evade
paywalls, DRM, geographic restrictions, enrollment rules, or locked-course
controls. Do not commit captured course material to this repository or attach it
to public issues.

The browser fallback uses an existing logged-in session only when the user has
authorized it. The workflow never exports that session into scripts.

## Development

```bash
python3 -m pip install -r requirements.txt -r requirements-dev.txt
python3 tools/validate_skill.py coursera-source-capture
python3 -m unittest discover -s tests -v
python3 tools/package_skill.py --version 0.1.0
```

Pull requests must use synthetic fixtures and preserve the lock-state, no-
credential, no-overwrite, and no-coursework-submission invariants. See
[`CONTRIBUTING.md`](CONTRIBUTING.md).

## Versioning

The repository uses semantic version tags. Push a tag such as `v0.1.0` after CI
passes; the release workflow packages only the installable skill directory and
publishes a SHA-256-addressed zip.

## License

MIT. See [`LICENSE`](LICENSE).
