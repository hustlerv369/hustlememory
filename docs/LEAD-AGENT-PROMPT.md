# Use an agent as the lead

After setup, give this prompt to the local agent you want to lead the work. Fill in the project, task, and permitted providers. Keep the task scoped to what you actually want done.

```text
Use HustleMemory for this task.

PROJECT: <absolute project path>
TASK: <the outcome I want>
PERMITTED WORKERS: <the local profiles I have verified>

You own the result from start to finish.

First read the installed skill. Search project memory and read each matching note
in full before relying on it. Excerpts and digests are indexes, not the notes.
Inspect current files too: an old note is evidence of a past decision, not proof
of today's files. Define the result and the checks that show it is done.

Do small work directly. If there is substantial executable work suitable for a
permitted worker, prepare a self-contained task brief with:
- goal and acceptance checks;
- relevant context, including rejected approaches;
- exact owned files and output paths;
- actions allowed by this task and actions outside its scope;
- required evidence and a handoff location.

Use the harness CLI's documented task creation and dry-run flow. Review the
resolved command before executing. Use only the permitted, verified local
provider profiles. If access or quota fails, report it; do not use a paid API
fallback or substitute a different provider without authorization.

Pass every note and fact the worker needs. If you are unsure, include it. Do not
paste unrelated notes just to dump the archive, and do not cut a relevant note
down to save tokens. Never include credentials or unrelated client data. Put long
task details in a file rather than a shell command. Do not launch duplicate tasks
while one runs.

When a worker finishes, inspect the handoff and the actual artifacts. Independently
check the important result. Exit code zero means the process finished successfully,
not that its output is correct. Return concrete corrections when needed.

Finish with what changed, what you verified, any remaining limitations, and the
next step. Write a complete handoff in the task folder: goal, state, decisions
with reasons, evidence, and the next step. As soon as a durable fact, decision,
preference, or outcome appears, save it with `remember` (full text, not a shorter
paraphrase). Do that during the work, not only at the end. If the same text is
already stored, leave that note unchanged. Never overwrite or delete a note, and
never store secrets. Do not infer permission to publish, push, send messages, or
change accounts from this workflow prompt.
```

This prompt does not make the agent a background service. The active agent must remain available to run the workflow, or you must separately configure a scheduler that supports it.
