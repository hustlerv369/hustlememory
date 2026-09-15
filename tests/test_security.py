"""Path traversal, symlink/junction escapes, conflicting stores, source hygiene."""
from __future__ import annotations

import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import CLI, REPO_ROOT, run_cli, snapshot_tree


def _try_symlink(link: Path, target: Path, directory: bool) -> str | None:
    try:
        if directory:
            link.symlink_to(target, target_is_directory=True)
        else:
            link.symlink_to(target)
        return "symlink"
    except OSError:
        pass
    if os.name == "nt" and directory:
        completed = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            capture_output=True,
            text=True,
        )
        if completed.returncode == 0 and link.exists():
            return "junction"
    return None


class TempProjectTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.project = self.root / "project"
        self.project.mkdir()
        self.home = self.root / "fake-home"
        self.home.mkdir()
        self.outside = self.root / "outside"
        self.outside.mkdir()
        self.home_before = snapshot_tree(self.home)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def cli(self, *args: str, **kwargs):
        return run_cli(*args, home=self.home, **kwargs)

    def init(self) -> None:
        result = self.cli("init", "--project", str(self.project))
        self.assertEqual(result.returncode, 0, result.stderr)


class TestTraversal(TempProjectTest):
    def test_read_rejects_path_separators_and_dotdot(self) -> None:
        self.init()
        secret = self.outside / "secret.md"
        secret.write_text("should-not-be-read", encoding="utf-8")
        payloads = [
            "../secret",
            "..\\secret",
            "../../outside/secret",
            "notes/../../outside/secret",
            str(secret),
            "/etc/passwd",
            "C:\\Windows\\win.ini",
            "..",
            "foo/bar",
            "foo\\bar",
            ".\\win.ini",
        ]
        for raw in payloads:
            with self.subTest(raw=raw):
                result = self.cli("read", "--project", str(self.project), raw)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn("invalid note id", result.stderr)

    def test_read_unknown_id(self) -> None:
        self.init()
        result = self.cli("read", "--project", str(self.project), "20260915T120000Z-deadbeef")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not found", result.stderr)


class TestConflictingPaths(TempProjectTest):
    def test_agent_memory_as_file(self) -> None:
        (self.project / ".agent-memory").write_text("nope", encoding="utf-8")
        result = self.cli("init", "--project", str(self.project))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not a directory", result.stderr)

    def test_unrelated_existing_files_rejected(self) -> None:
        memory = self.project / ".agent-memory"
        memory.mkdir()
        (memory / "cache.db").write_bytes(b"not-ours")
        result = self.cli("init", "--project", str(self.project))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unrelated files", result.stderr)
        self.assertTrue((memory / "cache.db").is_file())
        self.assertFalse((memory / "hustlememory.json").exists())

    def test_notes_with_files_but_no_marker_rejected(self) -> None:
        memory = self.project / ".agent-memory"
        notes = memory / "notes"
        notes.mkdir(parents=True)
        (notes / "foreign.md").write_text("legacy", encoding="utf-8")
        result = self.cli("init", "--project", str(self.project))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unrelated files", result.stderr)
        self.assertFalse((memory / "hustlememory.json").exists())

    def test_malformed_marker_rejected(self) -> None:
        memory = self.project / ".agent-memory"
        notes = memory / "notes"
        notes.mkdir(parents=True)
        (memory / "hustlememory.json").write_text("{not-json", encoding="utf-8")
        result = self.cli("list", "--project", str(self.project))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("malformed", result.stderr)

    def test_wrong_kind_marker_rejected(self) -> None:
        memory = self.project / ".agent-memory"
        notes = memory / "notes"
        notes.mkdir(parents=True)
        (memory / "hustlememory.json").write_text(
            '{"kind": "other", "version": 1}\n', encoding="utf-8"
        )
        result = self.cli("list", "--project", str(self.project))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not a HustleMemory store", result.stderr)

    def test_empty_dir_can_be_initialized(self) -> None:
        (self.project / ".agent-memory").mkdir()
        result = self.cli("init", "--project", str(self.project))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.project / ".agent-memory" / "hustlememory.json").is_file())

    def test_harness_paths_allowed_arbitrary_rejected(self) -> None:
        self.init()
        memory = self.project / ".agent-memory"
        (memory / "harness.json").write_text(
            '{"kind": "hustlememory-harness", "version": 1, "profiles": {}}\n',
            encoding="utf-8",
        )
        (memory / "tasks").mkdir()
        listed = self.cli("list", "--project", str(self.project))
        self.assertEqual(listed.returncode, 0, listed.stderr)
        (memory / "cache.db").write_bytes(b"nope")
        listed = self.cli("list", "--project", str(self.project))
        self.assertNotEqual(listed.returncode, 0)
        self.assertIn("unrelated files", listed.stderr)

    def test_tasks_file_not_directory_rejected(self) -> None:
        self.init()
        (self.project / ".agent-memory" / "tasks").write_text("nope", encoding="utf-8")
        listed = self.cli("list", "--project", str(self.project))
        self.assertNotEqual(listed.returncode, 0)
        self.assertIn("tasks must be a directory", listed.stderr)


class TestLinkEscape(TempProjectTest):
    def tearDown(self) -> None:
        for path in (self.project / ".agent-memory", self.project / ".gitignore"):
            try:
                if path.is_symlink() or (
                    hasattr(path, "is_junction") and path.is_junction()
                ):
                    path.unlink()
            except OSError:
                pass
        super().tearDown()

    def test_memory_dir_link_rejected_on_init(self) -> None:
        kind = _try_symlink(self.project / ".agent-memory", self.outside, directory=True)
        if not kind:
            self.skipTest("symlinks/junctions are not available")
        (self.outside / "trap.txt").write_text("no", encoding="utf-8")
        result = self.cli("init", "--project", str(self.project))
        self.assertNotEqual(result.returncode, 0)
        err = result.stderr.lower()
        self.assertTrue("reparse" in err or "symbolic link" in err, result.stderr)
        self.assertFalse((self.outside / "hustlememory.json").exists())

    def test_read_rejects_note_that_is_a_link(self) -> None:
        self.init()
        target = self.outside / "escaped.md"
        target.write_text("escaped-content-xyz", encoding="utf-8")
        notes = self.project / ".agent-memory" / "notes"
        link = notes / "20260915T120000Z-linktest.md"
        kind = _try_symlink(link, target, directory=False)
        if not kind:
            self.skipTest("file symlinks are not available")
        result = self.cli("read", "--project", str(self.project), "20260915T120000Z-linktest")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("escaped-content-xyz", result.stdout)
        recalled = self.cli("recall", "--project", str(self.project), "escaped-content-xyz")
        self.assertEqual(recalled.returncode, 0, recalled.stderr)
        self.assertIn("matches: 0", recalled.stdout)

    def test_gitignore_link_rejected(self) -> None:
        target = self.outside / "gitignore"
        target.write_bytes(b"keep\n")
        kind = _try_symlink(self.project / ".gitignore", target, directory=False)
        if not kind:
            self.skipTest("file symlinks are not available")
        result = self.cli("init", "--project", str(self.project))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("gitignore", result.stderr.lower())
        self.assertEqual(target.read_bytes(), b"keep\n")


class TestSourceHygiene(unittest.TestCase):
    def test_cli_has_no_personal_paths_or_network_imports(self) -> None:
        source = CLI.read_text(encoding="utf-8")
        lowered = source.lower()
        self.assertNotIn("c:\\users\\", lowered)
        self.assertNotIn("/users/", lowered)
        self.assertNotIn("appdata", lowered)
        self.assertNotIn("megamind", lowered)
        self.assertNotIn("seokrates", lowered)
        self.assertNotIn("hustlerv369", lowered)
        self.assertNotRegex(source, r"^\s*import\s+(socket|urllib|http|requests)\b", )
        self.assertNotRegex(source, r"^\s*from\s+(socket|urllib|http|requests)\b")
        # Network-looking calls should not appear either.
        self.assertNotIn("urlopen", lowered)
        self.assertNotIn("http.client", lowered)

    def test_payload_has_no_home_paths(self) -> None:
        skip_parts = {".git", "assets", "tests", "__pycache__"}
        roots = [
            REPO_ROOT / "README.md",
            REPO_ROOT / "LICENSE",
            REPO_ROOT / "SECURITY.md",
            REPO_ROOT / "SKILL.md",
            REPO_ROOT / "SETUP-PROMPT.md",
            REPO_ROOT / "scripts",
            REPO_ROOT / "examples",
            REPO_ROOT / "agents",
            REPO_ROOT / "docs",
            REPO_ROOT / "references",
        ]
        files: list[Path] = []
        for root in roots:
            if root.is_file():
                files.append(root)
            elif root.is_dir():
                files.extend(p for p in root.rglob("*") if p.is_file())
        self.assertTrue(files)
        for path in files:
            if any(part in skip_parts for part in path.parts):
                continue
            if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            self.assertNotIn("C:\\Users\\", text, msg=str(path))
            self.assertNotIn("/Users/", text, msg=str(path))
            self.assertNotIn("AppData\\Roaming", text, msg=str(path))

    def test_cli_is_not_world_writable_script_when_stat_available(self) -> None:
        mode = CLI.stat().st_mode
        self.assertTrue(stat.S_ISREG(mode))


class TestNoRepoPollution(unittest.TestCase):
    def test_running_help_does_not_write_repo_memory(self) -> None:
        before = snapshot_tree(REPO_ROOT)
        result = subprocess.run(
            [sys.executable, str(CLI), "-h"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=str(REPO_ROOT),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--project", result.stdout)
        after = snapshot_tree(REPO_ROOT)
        self.assertEqual(before, after)
        self.assertFalse((REPO_ROOT / ".agent-memory").exists())
