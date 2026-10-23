# Release validation

## V2

See [CHANGELOG.md](../CHANGELOG.md). `python -m unittest discover -s tests -v` — **75 tests passed** in this V2 change. The suite covers full-note reads, newest-first paging, accent-insensitive BM25, handoff search, `remember`, and harness capture of handoffs.

## v0.1.0

Checked on Windows with Python 3.13 on 2026-09-15.

## Automated checks

**54 tests passed.** Run them with `python -m unittest discover -s tests -v`.

The suite covers memory round trips, Unicode, bounded reads, project isolation,
symlink/junction escapes, conflicting stores, Git ignore negation, task dispatch,
profile confirmation, API environment rejection, literal argument handling,
nonzero exits, timeout, duplicate dispatch, interruption cleanup, and explicit
acceptance. Tests use temporary projects and fake Python workers.

Independent review added regressions for pre-existing output files, symlinked
logs/handoffs/locks, a state change before lock acquisition, Ctrl+C cleanup, and
a generic `!*` Git ignore rule that could expose a memory directory.

## Live provider check

A small Grok CLI task ran through `scripts/harness.py` using an already verified
subscription login and a child-process environment without API-key variables.
It read a fictional memory note and wrote a handoff with the correct currency
(`EUR`), next step, and constraint. The harness recorded
`completed_pending_review`; the handoff was inspected before `accept` was run.

The first launch was correctly blocked by unrelated API-key environment
variables. No API fallback was used. Private account files, task logs, and machine
paths are excluded from this repository.

## Scope of evidence

- The local `--help` interfaces of Grok, Codex, Claude Code, and Kimi were inspected.
- Only Grok received a live provider task through this release's harness.
- macOS/Linux are designed for but not runtime-tested in this release.
- No native voice, media, editor integration, background service, or cross-device
  synchronization is included.
- Review and pattern scanning found no creator-specific private paths or secrets
  in the public payload. This is not a guarantee that future user notes are safe
  to publish; keep project memory private.

The launcher is not a sandbox and cannot prove subscription billing from a
profile flag. Verify your own provider configuration before enabling execution.
