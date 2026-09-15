"""CLI behavior: init, list, recall, read, note, Unicode, gitignore, handoff."""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import run_cli, snapshot_tree


class TempProjectTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.project = self.root / "project"
        self.project.mkdir()
        self.home = self.root / "fake-home"
        self.home.mkdir()
        self.home_before = snapshot_tree(self.home)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def cli(self, *args: str, stdin: str | None = None, **kwargs):
        return run_cli(*args, home=self.home, stdin=stdin, **kwargs)

    def init(self, extra: tuple[str, ...] = ()) -> None:
        result = self.cli("init", "--project", str(self.project), *extra)
        self.assertEqual(result.returncode, 0, result.stderr)

    def assert_no_home_writes(self) -> None:
        self.assertEqual(snapshot_tree(self.home), self.home_before)


class TestInit(TempProjectTest):
    def test_requires_existing_project(self) -> None:
        missing = self.root / "nope"
        result = self.cli("init", "--project", str(missing))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does not exist", result.stderr)

    def test_rejects_file_as_project(self) -> None:
        target = self.root / "fileproj"
        target.write_text("x", encoding="utf-8")
        result = self.cli("init", "--project", str(target))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not a directory", result.stderr)

    def test_requires_project_flag(self) -> None:
        result = self.cli("init")
        self.assertEqual(result.returncode, 2)
        self.assert_no_home_writes()

    def test_creates_store_and_is_idempotent(self) -> None:
        first = self.cli("init", "--project", str(self.project))
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertIn("status: created", first.stdout)
        marker = self.project / ".agent-memory" / "hustlememory.json"
        notes = self.project / ".agent-memory" / "notes"
        self.assertTrue(marker.is_file())
        self.assertTrue(notes.is_dir())
        marker_bytes = marker.read_bytes()
        second = self.cli("init", "--project", str(self.project))
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn("status: exists", second.stdout)
        self.assertEqual(marker.read_bytes(), marker_bytes)
        self.assertTrue(marker_bytes)
        gitignore = (self.project / ".gitignore").read_bytes()
        self.assertEqual(gitignore.count(b"/.agent-memory/"), 1)
        self.assert_no_home_writes()

    def test_gitignore_preserves_existing_bytes(self) -> None:
        gitignore = self.project / ".gitignore"
        original = b"# keep CRLF\r\nsecret.bin\r\n# no trailing newline"
        gitignore.write_bytes(original)
        result = self.cli("init", "--project", str(self.project))
        self.assertEqual(result.returncode, 0, result.stderr)
        data = gitignore.read_bytes()
        self.assertTrue(data.startswith(original))
        self.assertEqual(data, original + b"\n/.agent-memory/\n")
        self.assertIn("gitignore: appended", result.stdout)
        self.assertIn("does not untrack", result.stderr)

    def test_gitignore_not_duplicated(self) -> None:
        gitignore = self.project / ".gitignore"
        gitignore.write_bytes(b"foo\n/.agent-memory/\nbar\n")
        before = gitignore.read_bytes()
        result = self.cli("init", "--project", str(self.project))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(gitignore.read_bytes(), before)
        self.assertIn("gitignore: present", result.stdout)

    def test_gitignore_negation_appends_final_ignore(self) -> None:
        gitignore = self.project / ".gitignore"
        gitignore.write_bytes(b"/.agent-memory/\n!/.agent-memory/\n")
        result = self.cli("init", "--project", str(self.project))
        self.assertEqual(result.returncode, 0, result.stderr)
        data = gitignore.read_bytes()
        self.assertTrue(data.startswith(b"/.agent-memory/\n!/.agent-memory/\n"))
        self.assertTrue(data.endswith(b"/.agent-memory/\n"))
        self.assertIn("gitignore: appended", result.stdout)
        marker = self.project / ".agent-memory" / "hustlememory.json"
        self.assertTrue(marker.is_file())
        git = shutil.which("git")
        if not git:
            return
        init = subprocess.run(
            [git, "init"],
            cwd=str(self.project),
            capture_output=True,
            text=True,
        )
        if init.returncode != 0:
            return
        check = subprocess.run(
            [git, "check-ignore", "-q", ".agent-memory/hustlememory.json"],
            cwd=str(self.project),
        )
        self.assertEqual(check.returncode, 0, "git check-ignore should treat the store as ignored")

    def test_no_gitignore_flag_leaves_file_alone(self) -> None:
        result = self.cli("init", "--project", str(self.project), "--no-gitignore")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.project / ".gitignore").exists())
        self.assertIn("gitignore: skipped", result.stdout)


class TestNotesAndHandoff(TempProjectTest):
    def test_note_list_read_roundtrip(self) -> None:
        self.init()
        wrote = self.cli(
            "note",
            "--project",
            str(self.project),
            "--title",
            "Retry budget",
            "Cap checkout retries at three.",
        )
        self.assertEqual(wrote.returncode, 0, wrote.stderr)
        note_id = None
        for line in wrote.stdout.splitlines():
            if line.startswith("wrote: "):
                note_id = line.split(" ", 1)[1]
        self.assertIsNotNone(note_id)
        listed = self.cli("list", "--project", str(self.project))
        self.assertEqual(listed.returncode, 0, listed.stderr)
        self.assertIn(note_id, listed.stdout)
        self.assertIn("Retry budget", listed.stdout)
        read = self.cli("read", "--project", str(self.project), note_id)
        self.assertEqual(read.returncode, 0, read.stderr)
        self.assertIn("Cap checkout retries at three.", read.stdout)
        self.assertIn("untrusted data", read.stderr)
        self.assert_no_home_writes()

    def test_note_from_stdin(self) -> None:
        self.init()
        wrote = self.cli(
            "note",
            "--project",
            str(self.project),
            "--title",
            "Stdin note",
            stdin="Body from stdin.\n",
        )
        self.assertEqual(wrote.returncode, 0, wrote.stderr)
        self.assertIn("wrote: ", wrote.stdout)

    def test_note_does_not_overwrite(self) -> None:
        self.init()
        a = self.cli("note", "--project", str(self.project), "--title", "A", "one")
        b = self.cli("note", "--project", str(self.project), "--title", "B", "two")
        self.assertEqual(a.returncode, 0, a.stderr)
        self.assertEqual(b.returncode, 0, b.stderr)
        id_a = a.stdout.splitlines()[0].split(" ", 1)[1]
        id_b = b.stdout.splitlines()[0].split(" ", 1)[1]
        self.assertNotEqual(id_a, id_b)
        notes = list((self.project / ".agent-memory" / "notes").glob("*.md"))
        self.assertEqual(len(notes), 2)

    def test_empty_note_rejected(self) -> None:
        self.init()
        result = self.cli("note", "--project", str(self.project), stdin="   \n")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("empty note", result.stderr)

    def test_unicode_roundtrip_without_pythonutf8(self) -> None:
        self.init()
        body = "České znaky 日本語 café 🧠 přihlášení"
        wrote = self.cli(
            "note",
            "--project",
            str(self.project),
            "--title",
            "Diakritika",
            body,
            set_pythonutf8=False,
        )
        self.assertEqual(wrote.returncode, 0, wrote.stderr)
        note_id = wrote.stdout.splitlines()[0].split(" ", 1)[1]
        read = self.cli(
            "read",
            "--project",
            str(self.project),
            note_id,
            set_pythonutf8=False,
        )
        self.assertEqual(read.returncode, 0, read.stderr)
        self.assertIn("České znaky", read.stdout)
        self.assertIn("日本語", read.stdout)
        self.assertIn("🧠", read.stdout)
        recalled = self.cli(
            "recall",
            "--project",
            str(self.project),
            "přihlášení",
            set_pythonutf8=False,
        )
        self.assertEqual(recalled.returncode, 0, recalled.stderr)
        self.assertIn(note_id, recalled.stdout)
        self.assertIn("matches: 1", recalled.stdout)

    def test_recall_is_lexical_not_outside_memory(self) -> None:
        self.init()
        decoy = self.project / "secret.md"
        decoy.write_text("unique-token-should-not-match pineapple-xyz", encoding="utf-8")
        (self.project / "docs").mkdir()
        (self.project / "docs" / "also.md").write_text(
            "unique-token-should-not-match", encoding="utf-8"
        )
        wrote = self.cli(
            "note",
            "--project",
            str(self.project),
            "--title",
            "Inside",
            "The adapter uses pineapple-xyz only in notes.",
        )
        self.assertEqual(wrote.returncode, 0, wrote.stderr)
        hit = self.cli("recall", "--project", str(self.project), "pineapple-xyz")
        self.assertEqual(hit.returncode, 0, hit.stderr)
        self.assertIn("matches: 1", hit.stdout)
        miss = self.cli("recall", "--project", str(self.project), "no-such-token-zzz")
        self.assertEqual(miss.returncode, 0, miss.stderr)
        self.assertIn("matches: 0", miss.stdout)

    def test_cross_agent_handoff(self) -> None:
        self.init()
        writer = self.cli(
            "note",
            "--project",
            str(self.project),
            "--title",
            "Handoff",
            "Ship the CLI before the skill docs.",
            extra_env={"HUSTLEMEMORY_AGENT": "codex"},
        )
        self.assertEqual(writer.returncode, 0, writer.stderr)
        note_id = writer.stdout.splitlines()[0].split(" ", 1)[1]
        listed = self.cli(
            "list",
            "--project",
            str(self.project),
            extra_env={"HUSTLEMEMORY_AGENT": "claude"},
        )
        self.assertEqual(listed.returncode, 0, listed.stderr)
        self.assertIn(note_id, listed.stdout)
        recalled = self.cli(
            "recall",
            "--project",
            str(self.project),
            "CLI",
            extra_env={"HUSTLEMEMORY_AGENT": "grok"},
        )
        self.assertEqual(recalled.returncode, 0, recalled.stderr)
        self.assertIn(note_id, recalled.stdout)
        read = self.cli(
            "read",
            "--project",
            str(self.project),
            note_id,
            extra_env={"HUSTLEMEMORY_AGENT": "grok"},
        )
        self.assertEqual(read.returncode, 0, read.stderr)
        self.assertIn("Ship the CLI before the skill docs.", read.stdout)
        self.assert_no_home_writes()

    def test_read_truncation_reported(self) -> None:
        self.init()
        huge = "alpha " * 40000
        wrote = self.cli(
            "note",
            "--project",
            str(self.project),
            "--title",
            "Huge",
            stdin=huge,
        )
        self.assertEqual(wrote.returncode, 0, wrote.stderr)
        note_id = wrote.stdout.splitlines()[0].split(" ", 1)[1]
        read = self.cli("read", "--project", str(self.project), note_id)
        self.assertEqual(read.returncode, 0, read.stderr)
        self.assertIn("truncated:", read.stderr)
        self.assertIn("truncated:", read.stdout)

    def test_commands_require_init(self) -> None:
        listed = self.cli("list", "--project", str(self.project))
        self.assertNotEqual(listed.returncode, 0)
        self.assertIn("no HustleMemory store", listed.stderr)


class TestNoGlobalWrites(TempProjectTest):
    def test_operations_stay_in_project(self) -> None:
        self.init()
        self.cli(
            "note",
            "--project",
            str(self.project),
            "--title",
            "Local",
            "only here",
        )
        outside = [p for p in self.root.iterdir() if p.name not in {"project", "fake-home"}]
        self.assertEqual(outside, [])
        self.assert_no_home_writes()
        repo_memory = Path(__file__).resolve().parents[1] / ".agent-memory"
        self.assertFalse(repo_memory.exists())
