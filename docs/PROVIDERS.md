# Connect your own local agents

HustleMemory does not resell model access, share subscriptions, or carry login tokens. Each person installs the providers they use and signs in through each provider's own supported flow.

## What a subscription profile means

A profile is a local command for an agent you have already installed. Confirm the command and authentication mode on your own machine before enabling execution. Being able to run `--help` proves that a CLI is present; it does not prove that your account has access or that a request will use subscription quota.

Do not paste API keys or OAuth tokens into a profile or prompt. Do not copy another person's authentication files. If your CLI is configured for an API account, the same executable may use metered billing even when you also have a chat subscription.

## CLI options observed during development

These option families were checked with local `--help` output on Windows on 2026-09-15. Recheck your installed version before using them. Availability and account terms can change.

| Local tool | Headless entry point | Context delivery |
|---|---|---|
| Grok CLI | `grok --prompt-file <file>` | Reads a task file; `--cwd` selects the project |
| Codex CLI | `codex exec <prompt>` | Prompt can direct it to read the task file; `-C` selects the project |
| Claude Code | `claude -p <prompt>` | Prompt can direct it to read the task file; run in the project directory |
| Kimi Code | `kimi -p <prompt>` | Prompt can direct it to read the task file; run in the project directory |

Do not blindly add permission-bypass flags to make a headless run succeed. Start with the provider's normal permissions and a small task. If the provider cannot perform a required action non-interactively, report the limitation and configure that action deliberately.

For Claude Code, the locally inspected `--bare` mode explicitly selected API-oriented authentication. It is not a shortcut for a subscription-backed profile.

## A useful first live test

After confirming your account and quota, give one installed agent a small fictional task: read a demo decision in full, remember it, and write a handoff in the designated task folder. Inspect the resulting file before enabling larger work.

Repeat for each provider you intend to use. Do not infer that a successful Grok test proves Claude, Codex, or Kimi authentication. The repository's automated tests use fake workers and do not consume provider quota.

## What remains outside this release

Native ChatGPT voice, image-generation subscriptions, browser media tools, scheduled cloud agents, and editor-specific interfaces require their own integrations. Shared memory and local task dispatch do not reproduce those host capabilities.

The working method is portable: keep the context, explicit task, ownership, handoff, and review contract. Verify each additional integration separately.
