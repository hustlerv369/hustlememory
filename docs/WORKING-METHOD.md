# The shared-memory working method

This guide describes the workflow behind HustleMemory. Everything here uses fictional examples. It is a method you can adopt with local coding agents, not a copy of a creator's private workspace.

## Start with the right project

An agent needs a precise project path, the current task, and access to relevant files. Pointing every task at one giant memory folder makes it easy to mix unrelated clients or products.

Use project-local memory. If two agents work on the same project, give both the same absolute path. If they run on different computers, file synchronization is a separate problem; this release does not implement it.

## Recall before asking again

Before starting work, and before asking a person to repeat a decision, search the project's notes (`recall`, then `read`). A short excerpt or the digest is only an index. Read the whole note when you might rely on it. Then check the current files: an old note is evidence of a past decision, not proof of today's runtime state.

If a note and the user's current request conflict, surface the conflict and follow the applicable current instruction. Do not quietly revive a rejected approach.

## Store decisions with reasons

A useful note explains what should remain true and why. Record the evidence or relevant file when available.

```markdown
# Demo shop currency
Decision: display prices in EUR.
Reason: the fictional demo has a single European storefront.
Applies to: the demo catalog and checkout preview.
Do not infer: tax rules, payment support, or production readiness.
Verify: inspect the rendered product price after each catalog change.
```

Store the decision with the reasoning, evidence, constraints, and outcome. Do not drop facts for brevity, and do not paste an unrelated chat transcript in place of that decision. As soon as the decision is known, run `remember` so it is not left only in the chat. If that text is already stored, `remember` leaves the existing note unchanged. If the decision changed, `remember` appends a new note and records `supersedes`; it does not edit the old one. Do not write credentials, private customer records, or unrelated personal information into memory. `remember` refuses text that looks like a secret and writes nothing in that case.

## Keep memory separate from today's handoff

Memory preserves context that will matter later. A handoff tells the next agent how to continue one unfinished task. A good handoff names the current state, the next action, and how to verify it.

Use [HANDOFF-TEMPLATE.md](HANDOFF-TEMPLATE.md). Say explicitly when a test was not run. A command that exited successfully is not proof that a feature works for a user.

## Assign work that another agent can actually execute

The agent receiving a task may not see the original conversation. Give it a self-contained brief:

- The intended outcome and acceptance criteria.
- The exact project and output paths.
- The files it owns and any files another worker is editing.
- Necessary decisions, rejected approaches, and constraints.
- The commands or observable behavior that will verify the result.
- A place to write its output and handoff.

Match the workflow to the task. A typo correction does not need a multi-agent run. A large audit benefits from a written brief and explicit evidence requirements. Any task that produces a decision still gets a complete memory note. Do not drop stored facts to save tokens.

## Separate bulk work from final judgment

One agent can do a large inventory or first implementation while another reviews decisive evidence. The person or agent that received the task owns the final result. Assigning it elsewhere does not complete it.

Choose providers according to your own access and costs. A subscription does not automatically include API usage. If an authorized provider is unavailable, report that rather than silently switching billing routes.

## Coordinate writes

A human-readable task board can record the task, owner, owned paths, and current status. It is a coordination convention, not an operating-system lock.

For simultaneous code edits, use separate files or isolated Git worktrees. Do not let two workers rewrite the same memory note concurrently. Check the CLI documentation for the actual storage guarantees; do not infer locking from an atomic file write.

## Verify and return precise corrections

Read the delivered output and test the important claim independently. Do not repeat an entire research project merely to prove that you reviewed it.

If something fails, return a concrete correction to the same task: the observed failure, expected behavior, and verification step. Track what was fixed. Never describe an untested draft as production-ready.

## Resume after a new chat

1. Open the same project.
2. Read the task handoff and relevant notes.
3. Inspect the current files and any uncommitted changes.
4. Restate the next step and important constraints.
5. Continue the task and verify the result.

The old chat may be unavailable. That is why the next step and the reasons behind decisions need to be written down.

## Keep the claim honest

HustleMemory provides a local file bridge and agent guidance. It does not merge model weights, guarantee recall, authenticate providers, or make a model obey every note. It does not measure token savings or guarantee lower bills. Its value is that important context has a clear home and a repeatable way to retrieve it.
