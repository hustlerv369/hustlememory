"""Shared helpers for HustleMemory CLI tests. Uses only temporary project dirs."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CLI = REPO_ROOT / "scripts" / "memory.py"


FORBIDDEN_TEST_ENV = (
    "GROK_API_KEY",
    "XAI_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "OPENROUTER_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "MOONSHOT_API_KEY",
    "KIMI_API_KEY",
    "MINIMAX_API_KEY",
)


def isolated_env(home: Path | None = None) -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    for name in FORBIDDEN_TEST_ENV:
        env.pop(name, None)
    if home is not None:
        home.mkdir(parents=True, exist_ok=True)
        env["HOME"] = str(home)
        env["USERPROFILE"] = str(home)
        env["APPDATA"] = str(home / "AppData" / "Roaming")
        env["LOCALAPPDATA"] = str(home / "AppData" / "Local")
        env["XDG_CONFIG_HOME"] = str(home / ".config")
        env["XDG_DATA_HOME"] = str(home / ".local" / "share")
        env["XDG_STATE_HOME"] = str(home / ".local" / "state")
    return env


def run_cli(
    *args: str,
    project: Path | None = None,
    stdin: str | None = None,
    home: Path | None = None,
    extra_env: dict[str, str] | None = None,
    set_pythonutf8: bool = True,
) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, str(CLI), *args]
    if project is not None and "--project" not in args:
        # Callers should pass --project explicitly; this branch is a safety net
        # that we do not use in tests.
        cmd.extend(["--project", str(project)])
    env = isolated_env(home)
    if not set_pythonutf8:
        env.pop("PYTHONUTF8", None)
        env.pop("PYTHONIOENCODING", None)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        cmd,
        input=stdin,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        cwd=str(REPO_ROOT),
    )


def snapshot_tree(root: Path) -> set[str]:
    items: set[str] = set()
    if not root.exists():
        return items
    for path in root.rglob("*"):
        try:
            rel = str(path.relative_to(root))
        except ValueError:
            continue
        items.add(rel)
    return items
