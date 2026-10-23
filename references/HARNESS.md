# HustleMemory harness

Local dispatch of **approved** tasks to CLI agents you already installed and
signed in. The harness is a subprocess runner. It is not a cloud, a hook, a
web UI, or a subscription reseller.

`--project` is required on every command. `run` is a dry-run unless you pass
`--execute`.

## What it stores

Under the same project store as memory:

```text
<project>/.agent-memory/harness.json
<project>/.agent-memory/tasks/<id>/task.md
<project>/.agent-memory/tasks/<id>/status.json
<project>/.agent-memory/tasks/<id>/handoff.md   # written by the worker
<project>/.agent-memory/tasks/<id>/stdout.log
<project>/.agent-memory/tasks/<id>/stderr.log
```

`harness.json` holds argv lists only. Never put API keys, tokens, or account
files in it.

## Commands

```text
python scripts/harness.py init --project <root>
python scripts/harness.py doctor --project <root>
python scripts/harness.py new --project <root> --title "Title" [--ref path] <description>
python scripts/harness.py run --project <root> --task <id> --profile <name>
python scripts/harness.py run --project <root> --task <id> --profile <name> --execute [--timeout SECONDS]
python scripts/harness.py status --project <root> [--task <id>]
python scripts/harness.py accept --project <root> --task <id>
```

`init` writes a template of **disabled** profiles (`subscription_confirmed: false`).
It does not enable anything and does not prove billing.

`doctor` checks whether `argv[0]` is discoverable on PATH. That is not proof of
login, quota, or subscription.

`new` writes a task directory. `--ref` paths must be project-relative regular
paths; they are recorded, not copied. The description is UTF-8 from arguments,
`--file`, or stdin. There is no reliable secret detector: do not put secrets in
the description.

`run` without `--execute` prints the exact argv and exits. `--execute` starts
that argv with `cwd` set to the selected project. stdout and stderr go to log
files, not RAM. The worker is not stopped on a timer unless `--timeout` is set.
Omit it, or pass 0, to wait until the worker exits. There is no maximum. On an
opt-in timeout the harness tries to kill the process tree (`taskkill /T` on
Windows, process group on POSIX). If the platform cannot kill children, the
parent is still killed; orphans are a documented limit.

`accept` records an explicit review decision by the responsible person or lead agent. It is never implied by exit code 0, and the command itself does not verify quality.

`status` without `--task` lists tasks newest first. `--limit 0` (the default) prints every task. Every page prints a `more:` line, including `more: 0 more results` when nothing remains. A smaller `--limit` prints `more: N more results, use --offset …` when rows remain.

When a run finishes with a non-empty `handoff.md`, the harness appends a memory note containing the full handoff text, the task id, the profile name, and the task state. The handoff file is not edited or deleted. If that text is already stored, the existing note is left unchanged. If the text looks like a secret, the note is not written and the handoff stays on disk in full. A saved profile that still sets `--max-turns` or `--no-subagents` produces a warning; new templates do not include those flags.

## Profiles

Each profile is a JSON object:

```json
{
  "subscription_confirmed": false,
  "argv": ["grok", "--cwd", "{project}", "--prompt-file", "{prompt_file}"]
}
```

Placeholders (string replace per argv item, no shell): `{prompt_file}`,
`{project}`, `{handoff}`.

No `shell=True`. No command-string parsing. Special characters in an argv item
stay one argument.

Set `subscription_confirmed` to `true` only after you confirm **that CLI's own
account lane** (subscription vs API). Missing `GROK_API_KEY` and friends does
**not** prove the CLI will bill a subscription. Recheck `your-cli --help` on
the installed version before trusting template flags.

Templates shipped disabled (recheck locally):

| Profile | argv0 | Notes |
|---|---|---|
| grok | `grok` | `--prompt-file {prompt_file} --cwd {project} --output-format streaming-json` (no turn cap and no `--no-subagents`) |
| codex | `codex` | `exec --json -C {project}` plus a prompt naming `{prompt_file}` and `{handoff}` |
| claude | `claude` | `-p` plus `--output-format json`. **Never `--bare`** (API-only). |
| kimi | `kimi` | `-p` plus `--output-format stream-json` |

No permission-bypass flags. Windows `.cmd`/`.bat`/`.ps1` and POSIX shell
scripts are rejected as `argv[0]`. Point at a native executable and pass the
script as a later argument (for example `node.exe` plus a verified JS file).

`--execute` fails closed if any of these environment variables are nonempty:
`GROK_API_KEY`, `XAI_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`,
`OPENROUTER_API_KEY`, `GEMINI_API_KEY`, `GOOGLE_API_KEY`, `MOONSHOT_API_KEY`,
`KIMI_API_KEY`, `MINIMAX_API_KEY`.

## Task states

| State | Meaning |
|---|---|
| `created` | Task written, not started |
| `running` | Lock held, process started |
| `completed_pending_review` | Worker exit code 0. **Not accepted.** |
| `failed` | Nonzero exit, or the process could not start |
| `timed_out` | Timeout; process tree kill attempted |
| `interrupted` | Ctrl+C interrupted the runner; owned process-tree cleanup attempted |
| `accepted` | Reviewer ran `accept` after checking the handoff and artifacts |

A terminal task is not rerun silently. Missing `handoff.md` after exit 0 still
leaves the task unaccepted. Concurrent `run --execute` on the same task is
blocked by an exclusive lock.

Nonzero worker exits return a nonzero harness exit code. Timeouts return 124;
interruption returns 130. Existing task output files are refused rather than
overwritten. After a machine crash or forcibly killed runner, a task may remain
marked running: inspect its PID and artifacts before creating a replacement task.
The harness does not silently resume or rerun it.

The harness does not read model transcripts beyond status fields (state, exit
code, whether `handoff.md` exists). Logs stay on disk.

## Privacy

`harness.py` does not upload files. **`--execute` starts a model CLI.** That
CLI may send the task, referenced files, and notes it chooses to read to its
provider. Do not claim data never leaves the computer once a provider CLI runs.

No built-in cross-device sync, native voice/image/video, or automatic
all-provider integration. See also [docs/PROVIDERS.md](../docs/PROVIDERS.md).

## Safety limits

- Harness bookkeeping stays under the selected `--project`. **The harness is not
  a sandbox.** A launched CLI uses its own permissions and may access other files
  or network services. Use that provider's permission controls and an isolated
  project when appropriate.
- Path traversal and symlink/reparse escapes are rejected for store and
  `--ref` paths.
- Unique task ids; task identity is the directory name.
- Note and config publishes use a temp file then an atomic directory update.
  That is not a guarantee against a **malicious** concurrent process replacing
  files in `.agent-memory`.
- New files use mode `0o600` on POSIX.
- There is no heuristic that a task description is free of secrets.
