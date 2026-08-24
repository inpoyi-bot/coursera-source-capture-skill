# Contributing

Contributions are welcome when they improve capture reliability without
weakening provenance, access, or learner-safety boundaries.

## Before opening a pull request

1. Keep changes narrow and explain the observed failure mode.
2. Use synthetic fixtures only. Do not commit Coursera course text, transcripts,
   screenshots, attachments, learner data, cookies, tokens, or signed URLs.
3. Preserve explicit lock handling: only `is_locked:false` is eligible for
   capture. Missing or non-boolean lock state remains unknown.
4. Preserve raw files byte-for-byte and keep readable outputs mechanical.
5. Do not add quiz answering, lab submission, DRM bypass, credential export, or
   browser-profile copying.
6. Add a regression test for parser, schema, or queue behavior changes.

## Local checks

```bash
python3 -m pip install -r requirements.txt -r requirements-dev.txt
python3 tools/validate_skill.py coursera-source-capture
python3 -m unittest discover -s tests -v
python3 tools/package_skill.py --version 0.0.0-test
```

Network tests are not part of CI because they would depend on a live course and
changing third-party endpoints. If an endpoint shape changes, document the
minimal credential-free response shape and failure class without attaching
course content.

## Change classification

- Patch: bug fix or documentation correction that does not change the source
  contract.
- Minor: backwards-compatible capture mode, script, or schema addition.
- Major: incompatible output schema, queue semantics, or safety-contract change.

Update `CHANGELOG.md` for user-visible changes. Maintainers should tag releases
only after all checks pass and a clean-install smoke test succeeds.
