"""Harness tests use a fake Python worker only. No installed AI CLIs."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import REPO_ROOT, isolated_env, run_cli, snapshot_tree

HARNESS = REPO_ROOT / "scripts" / "harness.py"

FAKE_WORKER = """
import pathlib
import sys
import time

mode = sys.argv[1]
handoff = pathlib.Path(sys.argv[2])
if mode == "sleep":
    time.sleep(30)
    sys.exit(0)
if mode == "fail":
    sys.stderr.buffer.write(b"worker-failed\\n")
    sys.exit(3)
if mode == "echo":
    proof = pathlib.Path(sys.argv[3])
    proof.write_text(repr(sys.argv), encoding="utf-8")
    handoff.write_text("# Handoff\\n\\nechoed\\n", encoding="utf-8")
    sys.exit(0)
handoff.write_text("# Handoff\\n\\nDone.\\n", encoding="utf-8")
sys.exit(0)
"""


def run_harness(*args: str, home: Path | None = None, stdin: str | None = None, extra_env=None):
    import subprocess

    env = isolated_env(home)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(HARNESS), *args],
        input=stdin,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        cwd=str(REPO_ROOT),
    )


class HarnessTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self._tmp.name)
        self.project = self.root / "project"
        self.project.mkdir()
        self.home = self.root / "fake-home"
        self.home.mkdir()
        self.home_before = snapshot_tree(self.home)
        self.worker = self.project / "fake_worker.py"
        self.worker.write_text(FAKE_WORKER, encoding="utf-8")
        self.proof = self.project / "argv-proof.txt"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def h(self, *args: str, **kwargs):
        kwargs.setdefault("home", self.home)
        return run_harness(*args, **kwargs)

    def assert_no_home_writes(self) -> None:
        self.assertEqual(snapshot_tree(self.home), self.home_before)

    def write_fake_profiles(self, extra: dict | None = None) -> None:
        path = self.project / ".agent-memory" / "harness.json"
        profiles = {
            "ok": {
                "subscription_confirmed": True,
                "argv": [sys.executable, str(self.worker), "ok", "{handoff}"],
            },
            "fail": {
                "subscription_confirmed": True,
                "argv": [sys.executable, str(self.worker), "fail", "{handoff}"],
            },
            "sleep": {
                "subscription_confirmed": True,
                "argv": [sys.executable, str(self.worker), "sleep", "{handoff}"],
            },
            "echo": {
                "subscription_confirmed": True,
                "argv": [
                    sys.executable,
                    str(self.worker),
                    "echo",
                    "{handoff}",
                    str(self.proof),
                    "a; rm -rf / && echo pwned",
                ],
            },
            "unconfirmed": {
                "subscription_confirmed": False,
                "argv": [sys.executable, str(self.worker), "ok", "{handoff}"],
            },
        }
        if extra:
            profiles.update(extra)
        payload = {
            "kind": "hustlememory-harness",
            "version": 1,
            "profiles": profiles,
        }
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def init_and_profiles(self) -> None:
        result = self.h("init", "--project", str(self.project))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.write_fake_profiles()

    def create_task(self, text: str = "Do the fictional demo change.") -> str:
        result = self.h(
            "new",
            "--project",
            str(self.project),
            "--title",
            "Demo",
            text,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        for line in result.stdout.splitlines():
            if line.startswith("created: "):
                return line.split(" ", 1)[1]
        self.fail(result.stdout)

    def test_init_template_is_unconfirmed(self) -> None:
        result = self.h("init", "--project", str(self.project))
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads((self.project / ".agent-memory" / "harness.json").read_text(encoding="utf-8"))
        self.assertEqual(data["kind"], "hustlememory-harness")
        for name, profile in data["profiles"].items():
            self.assertIs(profile["subscription_confirmed"], False, name)
            self.assertNotIn("--bare", profile["argv"])
        grok_argv = data["profiles"]["grok"]["argv"]
        self.assertNotIn("--max-turns", grok_argv)
        self.assertNotIn("--no-subagents", grok_argv)
        second = self.h("init", "--project", str(self.project))
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn("harness: exists", second.stdout)
        listed = run_cli("list", "--project", str(self.project), home=self.home)
        self.assertEqual(listed.returncode, 0, listed.stderr)
        self.assert_no_home_writes()

    def test_new_and_dry_run_does_not_execute(self) -> None:
        self.init_and_profiles()
        (self.project / "src").mkdir()
        (self.project / "src" / "app.py").write_text("# demo\n", encoding="utf-8")
        created = self.h(
            "new",
            "--project",
            str(self.project),
            "--title",
            "Demo",
            "--ref",
            "src/app.py",
            "Do the fictional demo change.",
        )
        self.assertEqual(created.returncode, 0, created.stderr)
        task_id = created.stdout.splitlines()[0].split(" ", 1)[1]
        dry = self.h(
            "run",
            "--project",
            str(self.project),
            "--task",
            task_id,
            "--profile",
            "ok",
        )
        self.assertEqual(dry.returncode, 0, dry.stderr)
        self.assertIn("dry-run:", dry.stdout)
        task_dir = self.project / ".agent-memory" / "tasks" / task_id
        self.assertFalse((task_dir / "stdout.log").exists())
        status = json.loads((task_dir / "status.json").read_text(encoding="utf-8"))
        self.assertEqual(status["state"], "created")
        self.assert_no_home_writes()

    def test_execute_success_handoff_and_accept(self) -> None:
        self.init_and_profiles()
        task_id = self.create_task()
        ran = self.h(
            "run",
            "--project",
            str(self.project),
            "--task",
            task_id,
            "--profile",
            "ok",
            "--execute",
        )
        self.assertEqual(ran.returncode, 0, ran.stderr)
        self.assertIn("state: completed_pending_review", ran.stdout)
        self.assertIn("pending_review", ran.stderr)
        st = self.h("status", "--project", str(self.project), "--task", task_id)
        self.assertEqual(st.returncode, 0, st.stderr)
        self.assertIn("state: completed_pending_review", st.stdout)
        self.assertIn("handoff_present: true", st.stdout)
        accepted = self.h("accept", "--project", str(self.project), "--task", task_id)
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        again = self.h(
            "run",
            "--project",
            str(self.project),
            "--task",
            task_id,
            "--profile",
            "ok",
            "--execute",
        )
        self.assertNotEqual(again.returncode, 0)
        self.assertIn("cannot be rerun", again.stderr)
        self.assert_no_home_writes()

    def test_nonzero_exit_failed(self) -> None:
        self.init_and_profiles()
        task_id = self.create_task()
        ran = self.h(
            "run",
            "--project",
            str(self.project),
            "--task",
            task_id,
            "--profile",
            "fail",
            "--execute",
        )
        self.assertNotEqual(ran.returncode, 0, ran.stderr)
        self.assertIn("state: failed", ran.stdout)
        self.assertIn("exit_code: 3", ran.stdout)
        accept = self.h("accept", "--project", str(self.project), "--task", task_id)
        self.assertNotEqual(accept.returncode, 0)

    def test_timeout(self) -> None:
        self.init_and_profiles()
        task_id = self.create_task()
        ran = self.h(
            "run",
            "--project",
            str(self.project),
            "--task",
            task_id,
            "--profile",
            "sleep",
            "--execute",
            "--timeout",
            "1",
        )
        self.assertNotEqual(ran.returncode, 0, ran.stderr)
        self.assertIn("state: timed_out", ran.stdout)

    def test_duplicate_dispatch_lock(self) -> None:
        self.init_and_profiles()
        task_id = self.create_task()
        env = isolated_env(self.home)
        first = subprocess.Popen(
            [
                sys.executable,
                str(HARNESS),
                "run",
                "--project",
                str(self.project),
                "--task",
                task_id,
                "--profile",
                "sleep",
                "--execute",
                "--timeout",
                "8",
            ],
            cwd=str(REPO_ROOT),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            time.sleep(1.0)
            second = self.h(
                "run",
                "--project",
                str(self.project),
                "--task",
                task_id,
                "--profile",
                "ok",
                "--execute",
            )
            self.assertNotEqual(second.returncode, 0, second.stdout)
            self.assertTrue(
                "lock" in second.stderr.lower() or "running" in second.stderr.lower(),
                second.stderr,
            )
        finally:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(first.pid)],
                    capture_output=True,
                    text=True,
                )
            else:
                first.kill()
            try:
                first.wait(timeout=8)
            except Exception:
                pass

    def test_unsafe_ref_rejected(self) -> None:
        self.init_and_profiles()
        outside = self.root / "outside.txt"
        outside.write_text("no", encoding="utf-8")
        result = self.h(
            "new",
            "--project",
            str(self.project),
            "--ref",
            "../outside.txt",
            "task",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("escape", result.stderr.lower() + " " + result.stderr)

    def test_shell_injection_stays_literal_argv(self) -> None:
        self.init_and_profiles()
        task_id = self.create_task()
        ran = self.h(
            "run",
            "--project",
            str(self.project),
            "--task",
            task_id,
            "--profile",
            "echo",
            "--execute",
        )
        self.assertEqual(ran.returncode, 0, ran.stderr)
        proof = self.proof.read_text(encoding="utf-8")
        self.assertIn("a; rm -rf / && echo pwned", proof)
        self.assertFalse((self.project / "pwned").exists())

    def test_api_env_fail_closed(self) -> None:
        self.init_and_profiles()
        task_id = self.create_task()
        ran = self.h(
            "run",
            "--project",
            str(self.project),
            "--task",
            task_id,
            "--profile",
            "ok",
            "--execute",
            extra_env={"GROK_API_KEY": "sk-test-not-real"},
        )
        self.assertNotEqual(ran.returncode, 0)
        self.assertIn("GROK_API_KEY", ran.stderr)
        task_dir = self.project / ".agent-memory" / "tasks" / task_id
        self.assertFalse((task_dir / "stdout.log").exists())
        status = json.loads((task_dir / "status.json").read_text(encoding="utf-8"))
        self.assertEqual(status["state"], "created")

    def test_unconfirmed_profile_cannot_execute(self) -> None:
        self.init_and_profiles()
        task_id = self.create_task()
        ran = self.h(
            "run",
            "--project",
            str(self.project),
            "--task",
            task_id,
            "--profile",
            "unconfirmed",
            "--execute",
        )
        self.assertNotEqual(ran.returncode, 0)
        self.assertIn("subscription_confirmed", ran.stderr)

    def test_cmd_wrapper_rejected(self) -> None:
        self.init_and_profiles()
        wrapper = self.project / "tool.cmd"
        wrapper.write_text("@echo off\n", encoding="utf-8")
        self.write_fake_profiles(
            extra={
                "cmdwrap": {
                    "subscription_confirmed": True,
                    "argv": [str(wrapper), "{handoff}"],
                }
            }
        )
        task_id = self.create_task()
        ran = self.h(
            "run",
            "--project",
            str(self.project),
            "--task",
            task_id,
            "--profile",
            "cmdwrap",
            "--execute",
        )
        self.assertNotEqual(ran.returncode, 0)
        self.assertIn("shell wrapper", ran.stderr)

    def test_bare_flag_rejected(self) -> None:
        self.h("init", "--project", str(self.project))
        self.write_fake_profiles(
            extra={
                "bare": {
                    "subscription_confirmed": True,
                    "argv": [sys.executable, "--bare", "{prompt_file}"],
                }
            }
        )
        task_id = self.create_task()
        ran = self.h(
            "run",
            "--project",
            str(self.project),
            "--task",
            task_id,
            "--profile",
            "bare",
        )
        self.assertNotEqual(ran.returncode, 0)
        self.assertIn("--bare", ran.stderr)

    def test_doctor_does_not_execute_worker(self) -> None:
        self.init_and_profiles()
        marker = self.project / "worker-ran.txt"
        self.assertFalse(marker.exists())
        doc = self.h("doctor", "--project", str(self.project))
        self.assertEqual(doc.returncode, 0, doc.stderr)
        self.assertIn("does not prove login", doc.stdout)
        self.assertIn("profile: ok", doc.stdout)
        self.assertFalse(marker.exists())
        self.assert_no_home_writes()

    def test_source_hygiene(self) -> None:
        source = HARNESS.read_text(encoding="utf-8")
        lowered = source.lower()
        self.assertNotIn("c:\\users\\", lowered)
        self.assertNotIn("/users/", lowered)
        self.assertNotIn("shell=true", lowered.replace(" ", ""))
        templates = source.split("TEMPLATE_PROFILES", 1)[1].split("class CLIError", 1)[0]
        self.assertNotIn("--bare", templates)
        self.assertNotIn("--dangerously-skip-permissions", templates)
        self.assertNotIn("--max-turns", templates)
        self.assertNotIn("--no-subagents", templates)
        self.assertIn("BYPASS_FLAGS", source)

    def test_v2_does_not_ship_a_short_worker_cap(self) -> None:
        scripts = str(REPO_ROOT / "scripts")
        if scripts not in sys.path:
            sys.path.insert(0, scripts)
        import harness

        self.assertEqual(harness.DEFAULT_TIMEOUT, 3600)
        self.assertEqual(harness.MAX_TIMEOUT, 86400)
        version = self.h("--version")
        self.assertEqual(version.returncode, 0, version.stderr)
        self.assertIn("V2", version.stdout)
        self.assertIn("2.0.0", version.stdout)

    def test_doctor_warns_when_a_saved_profile_caps_turns(self) -> None:
        result = self.h("init", "--project", str(self.project))
        self.assertEqual(result.returncode, 0, result.stderr)
        path = self.project / ".agent-memory" / "harness.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["profiles"]["grok"]["argv"].extend(["--max-turns", "20", "--no-subagents"])
        path.write_text(json.dumps(data), encoding="utf-8")
        doc = self.h("doctor", "--project", str(self.project))
        self.assertEqual(doc.returncode, 0, doc.stderr)
        self.assertIn("sets --max-turns", doc.stderr)
        self.assertIn("sets --no-subagents", doc.stderr)

    def test_status_lists_newest_first_and_pages(self) -> None:
        result = self.h("init", "--project", str(self.project))
        self.assertEqual(result.returncode, 0, result.stderr)
        tasks = self.project / ".agent-memory" / "tasks"
        for name, state in (
            ("20200101T000000Z-oldtask1", "created"),
            ("20260101T000000Z-newtask1", "accepted"),
        ):
            task_dir = tasks / name
            task_dir.mkdir()
            (task_dir / "status.json").write_text(
                json.dumps({"id": name, "state": state}) + "\n",
                encoding="utf-8",
            )
        page = self.h("status", "--project", str(self.project), "--limit", "1")
        self.assertEqual(page.returncode, 0, page.stderr)
        self.assertIn("20260101T000000Z-newtask1", page.stdout)
        self.assertNotIn("20200101T000000Z-oldtask1", page.stdout)
        self.assertIn("more: 1 more results, use --offset 1 --limit 1", page.stdout)
        rest = self.h(
            "status",
            "--project",
            str(self.project),
            "--offset",
            "1",
            "--limit",
            "1",
        )
        self.assertEqual(rest.returncode, 0, rest.stderr)
        self.assertIn("20200101T000000Z-oldtask1", rest.stdout)
        self.assertNotIn("20260101T000000Z-newtask1", rest.stdout)

    def test_execute_captures_handoff_into_a_note(self) -> None:
        self.init_and_profiles()
        task_id = self.create_task()
        ran = self.h(
            "run",
            "--project",
            str(self.project),
            "--task",
            task_id,
            "--profile",
            "ok",
            "--execute",
        )
        self.assertEqual(ran.returncode, 0, ran.stderr)
        self.assertIn("captured: ", ran.stdout)
        notes = list((self.project / ".agent-memory" / "notes").glob("*.md"))
        self.assertEqual(len(notes), 1)
        text = notes[0].read_text(encoding="utf-8")
        self.assertIn("Done.", text)
        self.assertIn('author: "ok"', text)
        self.assertIn(f"handoff:{task_id}", text)
        self.assertIn("tags: [\"handoff\"]", text)
        handoff = self.project / ".agent-memory" / "tasks" / task_id / "handoff.md"
        self.assertEqual(handoff.read_text(encoding="utf-8"), "# Handoff\n\nDone.\n")
        status = json.loads(
            (self.project / ".agent-memory" / "tasks" / task_id / "status.json").read_text(encoding="utf-8")
        )
        self.assertEqual(status["capture"], "wrote")
        self.assertEqual(status["captured_note"], notes[0].stem)

    def test_execute_does_not_copy_a_secret_handoff_into_notes(self) -> None:
        self.init_and_profiles()
        worker = self.project / "secret_worker.py"
        worker.write_text(
            "import pathlib, sys\n"
            "pathlib.Path(sys.argv[2]).write_text('api_key=supersecretvalue\\n', encoding='utf-8')\n",
            encoding="utf-8",
        )
        self.write_fake_profiles(
            extra={
                "leak": {
                    "subscription_confirmed": True,
                    "argv": [sys.executable, str(worker), "x", "{handoff}"],
                }
            }
        )
        task_id = self.create_task()
        ran = self.h(
            "run",
            "--project",
            str(self.project),
            "--task",
            task_id,
            "--profile",
            "leak",
            "--execute",
        )
        self.assertEqual(ran.returncode, 0, ran.stderr)
        self.assertIn("not copied into a note", ran.stderr)
        self.assertNotIn("supersecretvalue", ran.stderr)
        self.assertNotIn("supersecretvalue", ran.stdout)
        notes = list((self.project / ".agent-memory" / "notes").glob("*.md"))
        self.assertEqual(notes, [])
        handoff = self.project / ".agent-memory" / "tasks" / task_id / "handoff.md"
        self.assertEqual(handoff.read_text(encoding="utf-8"), "api_key=supersecretvalue\n")
