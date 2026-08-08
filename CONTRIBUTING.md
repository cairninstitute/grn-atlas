# Contributing to GRN Atlas

Thanks for your interest in contributing.

Before you submit code, please read this file together with
[CLA_POLICY.md](CLA_POLICY.md). This repository is source-available for
non-commercial use, and CAIRN Institute intends to preserve the ability to
commercialize the software separately.

## Before opening a pull request

- discuss substantial changes first through an issue or maintainer contact
- keep changes scoped and reviewable
- include tests when you change behavior
- update documentation when setup, testing, workflows, or skill behavior changes

## Development expectations

- run backend tests when changing API or data logic:
  `venv/bin/python -m pytest backend -q`
- run frontend tests when changing UI logic:
  `npm run test`
- if you change skill routing, prompts, or orchestration behavior, update the skill
  docs and relevant harness cases

## Contribution rights

By submitting a pull request, patch, issue attachment, or other contribution to this
repository, you represent that:

- you have the legal right to submit the contribution
- the contribution does not knowingly violate another party's intellectual property rights
- you are willing to license the contribution under the project terms described in
  [CLA_POLICY.md](CLA_POLICY.md)

If you cannot agree to those terms, do not submit the contribution.

## Review and acceptance

Maintainers may request edits, tests, documentation updates, or contribution-rights
confirmation before merging.

Submitting a contribution does not guarantee acceptance.
