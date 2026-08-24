# Security Policy

## Reporting

Use GitHub's private security-advisory feature for vulnerabilities that could
expose credentials, browser state, signed URLs, learner data, or unintended
course progress. Do not include real credentials or copyrighted course content
in the report; use redacted or synthetic evidence.

## Security boundaries

This project must never:

- request, export, persist, or transmit Coursera passwords, cookies, CAUTH,
  tokens, browser profiles, local storage, or session files;
- persist temporary signed download URLs;
- infer that an unknown lock state is unlocked;
- launch or submit labs, quizzes, assignments, coaches, or external tools;
- overwrite existing capture outputs without an explicit reviewed migration;
- upload captured course material to CI, issues, pull requests, or releases.

First-party web endpoints and browser-control capabilities can change without
notice. Treat unexpected redirects, HTML shells, authentication prompts, or
non-WebVTT responses as failures and stop before writing them as valid sources.
