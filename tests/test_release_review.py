"""Independent release regressions; no provider calls or real user data."""
import json
import os
import shutil
import subprocess
import sys
import unittest
from unittest.mock import patch

import test_harness as fixtures
from helpers import REPO_ROOT, isolated_env, run_cli

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import harness


class ReleaseReview(unittest.TestCase):
    setUp = fixtures.HarnessTest.setUp
    tearDown = fixtures.HarnessTest.tearDown
    h = fixtures.HarnessTest.h
    write_fake_profiles = fixtures.HarnessTest.write_fake_profiles
    init_and_profiles = fixtures.HarnessTest.init_and_profiles
    create_task = fixtures.HarnessTest.create_task

    def test_generic_negation_cannot_expose_memory(self):
        path = self.project / ".gitignore"
        original = b"/.agent-memory/\n!*\n"
        path.write_bytes(original)
        result = run_cli("init", "--project", str(self.project), home=self.home)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(path.read_bytes(), original + b"/.agent-memory/\n")
        if shutil.which("git"):
            subprocess.run(["git", "init", "-q", str(self.project)], check=True)
            check = subprocess.run(["git", "-C", str(self.project), "check-ignore", ".agent-memory/hustlememory.json"], capture_output=True)
            self.assertEqual(check.returncode, 0)

    def test_existing_output_is_never_truncated(self):
        self.init_and_profiles()
        task = self.create_task()
        log = self.project / ".agent-memory/tasks" / task / "stdout.log"
        log.write_text("preserve", encoding="utf-8")
        ran = self.h("run", "--project", str(self.project), "--task", task, "--profile", "ok", "--execute")
        self.assertNotEqual(ran.returncode, 0)
        self.assertEqual(log.read_text(), "preserve")

    def test_symlink_outputs_and_lock_are_rejected(self):
        self.init_and_profiles()
        outside = self.root / "private.txt"
        outside.write_text("preserve", encoding="utf-8")
        for name in ("stdout.log", "stderr.log", "handoff.md", "task.lock"):
            task = self.create_task()
            link = self.project / ".agent-memory/tasks" / task / name
            try:
                link.symlink_to(outside)
            except OSError:
                self.skipTest("file symlinks unavailable")
            ran = self.h("run", "--project", str(self.project), "--task", task, "--profile", "ok", "--execute")
            self.assertNotEqual(ran.returncode, 0, name)
            self.assertEqual(outside.read_text(), "preserve")

    def test_state_is_rechecked_after_lock(self):
        self.init_and_profiles()
        task = self.create_task()
        status_path = self.project / ".agent-memory/tasks" / task / "status.json"
        acquire = harness.TaskLock.acquire

        def completed_before_lock(lock):
            data = json.loads(status_path.read_text())
            data["state"] = harness.STATE_PENDING
            status_path.write_text(json.dumps(data))
            acquire(lock)

        with patch.dict(os.environ, isolated_env(self.home), clear=True), patch.object(harness.TaskLock, "acquire", completed_before_lock), patch.object(harness.subprocess, "Popen") as spawn:
            with self.assertRaises(harness.CLIError):
                harness.cmd_run(self.project, task, "ok", True, 5)
            spawn.assert_not_called()

    def test_interrupt_kills_worker_and_records_state(self):
        self.init_and_profiles()
        task = self.create_task()

        class InterruptedWorker:
            pid = 12345
            killed = False
            def wait(self, timeout=None):
                if not self.killed:
                    raise KeyboardInterrupt()
                return -9
            def poll(self):
                return -9 if self.killed else None

        worker = InterruptedWorker()
        def kill(proc):
            proc.killed = True

        with patch.dict(os.environ, isolated_env(self.home), clear=True), patch.object(harness.subprocess, "Popen", return_value=worker), patch.object(harness, "kill_process_tree", side_effect=kill):
            code = harness.cmd_run(self.project, task, "ok", True, 5)
        self.assertEqual(code, 130)
        self.assertTrue(worker.killed)
        status = json.loads((self.project / ".agent-memory/tasks" / task / "status.json").read_text())
        self.assertEqual(status["state"], "interrupted")
