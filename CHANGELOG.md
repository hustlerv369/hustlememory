# Changelog

## V2

Full memory access, plus auto-save. Search and read no longer drop notes, bytes, or matches. New facts are appended as soon as they are known. Store layout version stays 1, so existing `.agent-memory` folders keep opening.

### Removed or disabled limits

- Recall scans every note and every task handoff. There is no file cap and no per-note byte cap inside the in-memory safety ceiling.
- `read` prints the entire note or handoff. It does not stop at 64 KiB.
- List, recall, digest, and harness status page with `--limit` and `--offset`. Remaining rows are reported (`more: N more results, use --offset …`). `--limit 0` prints every row. List and status default to every row.
- Titles are stored in full. The old 120-character title cut is gone.
- The Grok worker template no longer sets `--max-turns 20` or `--no-subagents`. A saved profile that still has those flags gets a warning.
- The default harness timeout is 3600 seconds. `--timeout` still accepts 1–86400. On timeout, files already written stay on disk.

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
- When a harness task ends with a non-empty handoff, that handoff is copied into a new note. The handoff file is not edited or deleted. Secrets and files that cannot be stored whole are not copied, and the command says so.

### Still rejected on purpose

- A new note larger than 256 KiB is rejected and is not stored in part.
- Search and indexes refuse a single file above 64 MiB instead of returning a partial result. `read` still streams that file in full. The file is not modified.
