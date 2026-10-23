# Changelog

## V2

Full memory access, plus auto-save. Search and read no longer drop notes, bytes, or matches. New facts are appended as soon as they are known. Store layout version stays 1, so existing `.agent-memory` folders keep opening.

### Removed or disabled limits

- Recall scans every note and every task handoff. There is no file cap and no per-note byte cap.
- `read` prints the entire note or handoff. Search and duplicate checks stream the file, so a large note stays fully searchable.
- A note of any size is stored in full. The old 256 KiB rejection is gone.
- List, recall, digest, and harness status page with `--limit` and `--offset`. Every page prints a `more:` line. When rows remain it gives the next offset. When the page is complete it prints `more: 0 more results`. `--limit 0` prints every row. List and status default to every row.
- Titles are stored in full. The old 120-character title cut is gone.
- The Grok worker template no longer sets `--max-turns 20` or `--no-subagents`. A saved profile that still has those flags gets a warning.
- The harness does not stop a worker on a timer unless `--timeout` is set. Omit it, or pass 0, to wait until the worker exits. There is no maximum. On an opt-in timeout, files already written stay on disk.

### Retrieval

- Notes and handoffs are ordered newest first when listing.
- Recall ranks with BM25 (length-normalized). Equal scores favor newer entries.
- Search is accent-insensitive. One-character terms match whole words.
- `--tag` filters list, recall, and digest. `note` and `remember` store tags.
- `digest` prints a recent index with links to the full entries. It does not replace or summarize notes.
- Excerpts are labeled previews. Each hit includes the `read` command for the full text.

### Auto-save

- `remember` appends a note with author, source, and timestamp. If the same text is already stored (accent- and whitespace-insensitive), it prints the existing id and does not rewrite anything. A different body with the same title becomes a new note with `supersedes`. Explicit `--related` and `--supersedes` links are also new notes; the older notes stay unchanged.
- `remember` refuses private keys, cloud key ids, common token prefixes, and credential assignments. Nothing is written in that case.
- When a harness task ends with a non-empty handoff, that handoff is copied into a new note. The copy is streamed, so a long handoff is stored in full. The handoff file is not edited or deleted. A handoff that looks like a secret is not copied, and the command says so. The handoff file stays on disk.

### Still rejected on purpose

- `remember`, and harness capture of a handoff, refuse text that looks like a private key, a cloud key id, a common token prefix, or a credential assignment. Nothing is written in that case. This is a privacy rule, not a size limit.
- The store marker is still checked for valid JSON, kind, and layout version, so a foreign directory is not treated as a HustleMemory store. Its size is not a reason to refuse it. Layout version stays 1.
