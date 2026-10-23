"""V2 memory access: full reads, no silent caps, ranked and accent-insensitive search."""
from __future__ import annotations

import io
import json
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import REPO_ROOT
from test_cli import TempProjectTest

SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import memory  # noqa: E402


class MemoryV2Test(TempProjectTest):
    def write_raw_note(
        self,
        note_id: str,
        body: str,
        title: str | None = None,
        created: str | None = None,
        tags: list[str] | None = None,
    ) -> None:
        notes = self.project / ".agent-memory" / "notes"
        notes.mkdir(parents=True, exist_ok=True)
        tag_line = ""
        if tags:
            tag_line = "tags: " + json.dumps(tags, ensure_ascii=False) + "\n"
        content = (
            "---\n"
            f"id: {note_id}\n"
            f"title: {title or note_id}\n"
            f"created: {created or '2020-01-01T00:00:00Z'}\n"
            f"{tag_line}"
            "---\n\n"
            f"{body}\n"
        )
        (notes / f"{note_id}.md").write_text(content, encoding="utf-8")

    def test_version_is_v2(self) -> None:
        result = self.cli("--version")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("HustleMemory V2 (2.0.0)", result.stdout)

    def test_source_has_no_silent_memory_caps(self) -> None:
        source = (SCRIPTS / "memory.py").read_text(encoding="utf-8")
        for needle in (
            "MAX_SCAN_FILES",
            "MAX_SCAN_BYTES",
            "MAX_READ_BYTES",
            "MAX_RECALL_RESULTS",
            "MAX_LIST_ENTRIES",
            "MAX_TITLE_CHARS",
            "truncated:",
        ):
            self.assertNotIn(needle, source, needle)

    def test_list_is_newest_first_and_unlimited_by_default(self) -> None:
        self.init()
        self.write_raw_note(
            "20200101T000000Z-oldnote1",
            "older decision",
            created="2020-01-01T00:00:00Z",
        )
        self.write_raw_note(
            "20230101T000000Z-midnote1",
            "middle decision",
            created="2023-01-01T00:00:00Z",
        )
        self.write_raw_note(
            "20260101T000000Z-newnote1",
            "newest decision",
            created="2026-01-01T00:00:00Z",
        )
        listed = self.cli("list", "--project", str(self.project))
        self.assertEqual(listed.returncode, 0, listed.stderr)
        self.assertIn("showing: 3 of 3", listed.stdout)
        self.assertNotIn("more:", listed.stdout)
        self.assertLess(
            listed.stdout.index("20260101T000000Z-newnote1"),
            listed.stdout.index("20230101T000000Z-midnote1"),
        )
        self.assertLess(
            listed.stdout.index("20230101T000000Z-midnote1"),
            listed.stdout.index("20200101T000000Z-oldnote1"),
        )
        page = self.cli("list", "--project", str(self.project), "--limit", "1")
        self.assertEqual(page.returncode, 0, page.stderr)
        self.assertIn("20260101T000000Z-newnote1", page.stdout)
        self.assertNotIn("20230101T000000Z-midnote1", page.stdout)
        self.assertIn("more: 2 more results, use --offset 1 --limit 1", page.stdout)
        self.assertIn("more: 2 more results, use --offset 1 --limit 1", page.stderr)
        nxt = self.cli(
            "list",
            "--project",
            str(self.project),
            "--offset",
            "1",
            "--limit",
            "1",
        )
        self.assertIn("20230101T000000Z-midnote1", nxt.stdout)
        self.assertNotIn("20260101T000000Z-newnote1", nxt.stdout)

    def test_recall_searches_every_note_including_the_newest(self) -> None:
        self.init()
        for index in range(205):
            note_id = f"20200101T000000Z-n{index:04d}"
            body = "filler-word only"
            if index == 204:
                note_id = "20260101T000000Z-newest"
                body = "filler-word newest-decision-token"
            self.write_raw_note(note_id, body, created="2020-01-01T00:00:00Z")
        self.write_raw_note(
            "20260101T000000Z-newest",
            "filler-word newest-decision-token",
            created="2026-01-01T00:00:00Z",
        )
        found = self.cli(
            "recall",
            "--project",
            str(self.project),
            "newest-decision-token",
        )
        self.assertEqual(found.returncode, 0, found.stderr)
        self.assertIn("matches: 1", found.stdout)
        self.assertIn("20260101T000000Z-newest", found.stdout)
        self.assertIn("scanned: 205", found.stdout)
        self.assertNotIn("truncated:", found.stdout)
        self.assertNotIn("truncated:", found.stderr)
        paged = self.cli("recall", "--project", str(self.project), "filler-word")
        self.assertEqual(paged.returncode, 0, paged.stderr)
        self.assertIn("matches: 205", paged.stdout)
        self.assertIn("showing: 100 of 205", paged.stdout)
        self.assertIn("more: 105 more results, use --offset 100 --limit 100", paged.stdout)
        everything = self.cli(
            "recall",
            "--project",
            str(self.project),
            "--limit",
            "0",
            "filler-word",
        )
        self.assertEqual(everything.returncode, 0, everything.stderr)
        self.assertIn("showing: 205 of 205", everything.stdout)
        self.assertNotIn("more:", everything.stdout)
        self.assertEqual(everything.stdout.count("\n--- note "), 205)

    def test_recall_and_read_include_text_past_the_old_byte_cap(self) -> None:
        self.init()
        body = ("x" * 70000) + "\nunique-tail-token-xyz\n"
        wrote = self.cli(
            "note",
            "--project",
            str(self.project),
            "--title",
            "Tail",
            stdin=body,
        )
        self.assertEqual(wrote.returncode, 0, wrote.stderr)
        note_id = wrote.stdout.splitlines()[0].split(" ", 1)[1]
        found = self.cli(
            "recall",
            "--project",
            str(self.project),
            "unique-tail-token-xyz",
        )
        self.assertEqual(found.returncode, 0, found.stderr)
        self.assertIn("matches: 1", found.stdout)
        self.assertIn(note_id, found.stdout)
        self.assertIn(f"full: read {note_id}", found.stdout)
        read = self.cli("read", "--project", str(self.project), note_id)
        self.assertEqual(read.returncode, 0, read.stderr)
        self.assertIn("unique-tail-token-xyz", read.stdout)
        self.assertIn("x" * 70000, read.stdout)
        self.assertNotIn("truncated:", read.stdout)

    def test_oversized_note_is_rejected_without_a_partial_write(self) -> None:
        self.init()
        body = "z" * ((256 * 1024) + 1)
        result = self.cli("note", "--project", str(self.project), stdin=body)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not stored", result.stderr)
        self.assertIn("not shortened", result.stderr)
        self.assertEqual(list((self.project / ".agent-memory" / "notes").glob("*.md")), [])

    def test_search_safety_ceiling_does_not_hide_or_alter_the_file(self) -> None:
        self.init()
        note_id = "20260101T000000Z-bigfile1"
        path = self.project / ".agent-memory" / "notes" / f"{note_id}.md"
        path.write_text("unique-big-token\n" + ("x" * 80), encoding="utf-8")
        original = path.read_bytes()
        previous = memory.SAFETY_READ_BYTES
        memory.SAFETY_READ_BYTES = 32
        try:
            read_out = io.StringIO()
            read_err = io.StringIO()
            with redirect_stdout(read_out), redirect_stderr(read_err):
                read_code = memory.main(
                    ["read", "--project", str(self.project), note_id]
                )
            self.assertEqual(read_code, 0, read_err.getvalue())
            self.assertIn("unique-big-token", read_out.getvalue())
            recall_out = io.StringIO()
            recall_err = io.StringIO()
            with redirect_stdout(recall_out), redirect_stderr(recall_err):
                recall_code = memory.main(
                    ["recall", "--project", str(self.project), "unique-big-token"]
                )
            self.assertNotEqual(recall_code, 0)
            self.assertNotIn("unique-big-token", recall_out.getvalue())
            self.assertIn("no partial results", recall_err.getvalue())
            self.assertEqual(path.read_bytes(), original)
        finally:
            memory.SAFETY_READ_BYTES = previous

    def test_accent_insensitive_search_and_single_letter_terms(self) -> None:
        self.init()
        self.write_raw_note(
            "20260101T000000Z-czech01",
            "Schválené rozhodnutí o ceně.",
            title="Cena",
        )
        self.write_raw_note(
            "20260101T000000Z-plan0001",
            "Choose plan C for the rollout.",
            title="Plan",
        )
        self.write_raw_note(
            "20260101T000000Z-catalog1",
            "The project catalog lists products.",
            title="Catalog",
        )
        czech = self.cli("recall", "--project", str(self.project), "rozhodnuti")
        self.assertEqual(czech.returncode, 0, czech.stderr)
        self.assertIn("matches: 1", czech.stdout)
        self.assertIn("20260101T000000Z-czech01", czech.stdout)
        letter = self.cli("recall", "--project", str(self.project), "C")
        self.assertEqual(letter.returncode, 0, letter.stderr)
        self.assertIn("20260101T000000Z-plan0001", letter.stdout)
        self.assertNotIn("20260101T000000Z-catalog1", letter.stdout)
        self.assertNotIn("20260101T000000Z-czech01", letter.stdout)

    def test_bm25_ranks_a_short_decision_above_a_long_repetition(self) -> None:
        self.init()
        self.write_raw_note(
            "20200101T000000Z-longnote",
            ("billing " * 4000) + "invoice appears once in a long note",
            title="Long",
            created="2020-01-01T00:00:00Z",
        )
        self.write_raw_note(
            "20200102T000000Z-shortnote",
            "Decision: invoice monthly.",
            title="Short",
            created="2020-01-02T00:00:00Z",
        )
        found = self.cli("recall", "--project", str(self.project), "invoice")
        self.assertEqual(found.returncode, 0, found.stderr)
        self.assertIn("matches: 2", found.stdout)
        self.assertIn("ranking: bm25", found.stdout)
        self.assertLess(
            found.stdout.index("20200102T000000Z-shortnote"),
            found.stdout.index("20200101T000000Z-longnote"),
        )

    def test_tags_filter_list_recall_and_digest(self) -> None:
        self.init()
        wrote = self.cli(
            "note",
            "--project",
            str(self.project),
            "--title",
            "Currency",
            "--tag",
            "Billing",
            "--tag",
            "eu",
            "Price in EUR.",
        )
        self.assertEqual(wrote.returncode, 0, wrote.stderr)
        note_id = wrote.stdout.splitlines()[0].split(" ", 1)[1]
        other = self.cli(
            "note",
            "--project",
            str(self.project),
            "--title",
            "Other",
            "--tag",
            "docs",
            "Unrelated note.",
        )
        other_id = other.stdout.splitlines()[0].split(" ", 1)[1]
        listed = self.cli("list", "--project", str(self.project), "--tag", "billing")
        self.assertEqual(listed.returncode, 0, listed.stderr)
        self.assertIn(note_id, listed.stdout)
        self.assertNotIn(other_id, listed.stdout)
        self.assertIn("Billing,eu", listed.stdout)
        missed = self.cli("recall", "--project", str(self.project), "--tag", "nope", "EUR")
        self.assertEqual(missed.returncode, 0, missed.stderr)
        self.assertIn("matches: 0", missed.stdout)
        hit = self.cli("recall", "--project", str(self.project), "--tag", "eu", "EUR")
        self.assertIn("matches: 1", hit.stdout)
        self.assertIn(note_id, hit.stdout)
        digest = self.cli("digest", "--project", str(self.project), "--tag", "billing")
        self.assertEqual(digest.returncode, 0, digest.stderr)
        self.assertIn("not a summary", digest.stdout)
        self.assertIn(note_id, digest.stdout)
        self.assertIn(f"full: read {note_id}", digest.stdout)
        self.assertNotIn(other_id, digest.stdout)

    def test_long_title_is_stored_in_full(self) -> None:
        self.init()
        title = "T" * 200
        wrote = self.cli(
            "note",
            "--project",
            str(self.project),
            "--title",
            title,
            "Body stays intact.",
        )
        self.assertEqual(wrote.returncode, 0, wrote.stderr)
        note_id = wrote.stdout.splitlines()[0].split(" ", 1)[1]
        read = self.cli("read", "--project", str(self.project), note_id)
        self.assertIn(title, read.stdout)
        self.assertIn("Body stays intact.", read.stdout)

    def test_recall_searches_handoffs_and_read_prints_them(self) -> None:
        self.init()
        task_id = "20260102T000000Z-task01"
        task_dir = self.project / ".agent-memory" / "tasks" / task_id
        task_dir.mkdir(parents=True)
        (task_dir / "handoff.md").write_text(
            "# Done\n\nunique-handoff-token-xyz\n",
            encoding="utf-8",
        )
        found = self.cli(
            "recall",
            "--project",
            str(self.project),
            "unique-handoff-token-xyz",
        )
        self.assertEqual(found.returncode, 0, found.stderr)
        self.assertIn("matches: 1", found.stdout)
        self.assertIn(task_id, found.stdout)
        self.assertIn(f"full: read --handoff {task_id}", found.stdout)
        notes_only = self.cli(
            "recall",
            "--project",
            str(self.project),
            "--source",
            "notes",
            "unique-handoff-token-xyz",
        )
        self.assertIn("matches: 0", notes_only.stdout)
        read = self.cli(
            "read",
            "--project",
            str(self.project),
            "--handoff",
            task_id,
        )
        self.assertEqual(read.returncode, 0, read.stderr)
        self.assertIn("unique-handoff-token-xyz", read.stdout)
        self.assertIn("untrusted data", read.stderr)

    def test_symlinked_handoff_is_not_searched(self) -> None:
        self.init()
        outside = self.root / "outside.md"
        outside.write_text("escaped-handoff-token\n", encoding="utf-8")
        task_dir = self.project / ".agent-memory" / "tasks" / "20260103T000000Z-linktask"
        task_dir.mkdir(parents=True)
        link = task_dir / "handoff.md"
        try:
            link.symlink_to(outside)
        except OSError:
            self.skipTest("symlinks are not available")
        found = self.cli(
            "recall",
            "--project",
            str(self.project),
            "escaped-handoff-token",
        )
        self.assertEqual(found.returncode, 0, found.stderr)
        self.assertIn("matches: 0", found.stdout)
        self.assertNotIn("--- handoff", found.stdout)
        self.assertNotIn("--- note", found.stdout)

    def test_remember_skips_exact_duplicate_and_links_a_change(self) -> None:
        self.init()
        first = self.cli(
            "remember",
            "--project",
            str(self.project),
            "--title",
            "Rozhodnutí",
            "--author",
            "grok",
            "--tag",
            "pricing",
            "Schválené rozhodnutí o ceně je EUR.",
        )
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertIn("wrote: ", first.stdout)
        note_id = first.stdout.splitlines()[0].split(" ", 1)[1]
        path = self.project / ".agent-memory" / "notes" / f"{note_id}.md"
        before = path.read_bytes()
        self.assertIn('author: "grok"', before.decode("utf-8"))
        self.assertIn('source: "remember"', before.decode("utf-8"))
        again = self.cli(
            "remember",
            "--project",
            str(self.project),
            "--title",
            "rozhodnuti",
            "Schvalene   rozhodnuti o cene je EUR.",
        )
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertIn(f"duplicate: {note_id}", again.stdout)
        self.assertIn("unchanged:", again.stdout)
        self.assertNotIn("wrote: ", again.stdout)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(len(list((self.project / ".agent-memory" / "notes").glob("*.md"))), 1)
        changed = self.cli(
            "remember",
            "--project",
            str(self.project),
            "--title",
            "rozhodnuti",
            "Schválené rozhodnutí o ceně je CZK.",
        )
        self.assertEqual(changed.returncode, 0, changed.stderr)
        self.assertIn("wrote: ", changed.stdout)
        self.assertIn(f"supersedes: {note_id}", changed.stdout)
        self.assertEqual(path.read_bytes(), before)
        new_id = changed.stdout.splitlines()[0].split(" ", 1)[1]
        new_text = (self.project / ".agent-memory" / "notes" / f"{new_id}.md").read_text(encoding="utf-8")
        self.assertIn("Schválené rozhodnutí o ceně je CZK.", new_text)
        self.assertIn(f"supersedes: {note_id}", new_text)
        labeled = self.cli(
            "remember",
            "--project",
            str(self.project),
            "--title",
            "Currency label",
            "Schválené rozhodnutí o ceně je EUR.",
        )
        self.assertEqual(labeled.returncode, 0, labeled.stderr)
        self.assertIn("wrote: ", labeled.stdout)
        self.assertIn(f"related: {note_id}", labeled.stdout)
        self.assertEqual(path.read_bytes(), before)

    def test_remember_refuses_secrets_and_keeps_ordinary_password_prose(self) -> None:
        self.init()
        secret = self.cli(
            "remember",
            "--project",
            str(self.project),
            "--title",
            "Keys",
            "api_key=supersecretvalue",
        )
        self.assertNotEqual(secret.returncode, 0)
        self.assertIn("Nothing was written", secret.stderr)
        self.assertNotIn("supersecretvalue", secret.stderr)
        self.assertNotIn("supersecretvalue", secret.stdout)
        self.assertEqual(list((self.project / ".agent-memory" / "notes").glob("*.md")), [])
        prose = self.cli(
            "remember",
            "--project",
            str(self.project),
            "--title",
            "Policy",
            "The password policy is 12 characters.",
            extra_env={"HUSTLEMEMORY_AGENT": "claude"},
        )
        self.assertEqual(prose.returncode, 0, prose.stderr)
        self.assertIn("wrote: ", prose.stdout)
        note_id = prose.stdout.splitlines()[0].split(" ", 1)[1]
        text = (self.project / ".agent-memory" / "notes" / f"{note_id}.md").read_text(encoding="utf-8")
        self.assertIn("The password policy is 12 characters.", text)
        self.assertIn('author: "claude"', text)

    def test_remember_does_not_write_when_the_link_target_is_missing(self) -> None:
        self.init()
        result = self.cli(
            "remember",
            "--project",
            str(self.project),
            "--title",
            "Missing link",
            "--supersedes",
            "20260101T000000Z-missing1",
            "A new fact that should not be stored yet.",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("note not found", result.stderr)
        self.assertEqual(list((self.project / ".agent-memory" / "notes").glob("*.md")), [])


if __name__ == "__main__":
    unittest.main()
