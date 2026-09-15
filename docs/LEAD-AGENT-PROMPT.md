# Use an agent as the lead

After setup, give this prompt to the local agent you want to lead the work. Fill in the project, task, and permitted providers. Keep the task scoped to what you actually want done.

```text
Use HustleMemory for this task.

PROJECT: <absolute project path>
TASK: <the outcome I want>
PERMITTED WORKERS: <the local profiles I have verified>

You own the result from start to finish.

First read the installed skill and relevant project memory. Inspect current files
before relying on an old note. Identify the smallest useful result and its checks.

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

Pass only relevant context. Do not copy the whole memory archive into the prompt.
Never include credentials or unrelated client data. Put long task details in a
file rather than a shell command. Do not launch duplicate tasks while one runs.

When a worker finishes, inspect the handoff and the actual artifacts. Independently
check the important result. Exit code zero means the process finished successfully,
not that its output is correct. Return concrete corrections when needed.

Finish with what changed, what you verified, any remaining limitations, and the
next step. Save a concise handoff in the task folder. Update durable project memory
only when permitted by my request and your agent's rules. Do not infer permission
to publish, push, send messages, or change accounts from this workflow prompt.
```

This prompt does not make the agent a background service. The active agent must remain available to run the workflow, or you must separately configure a scheduler that supports it.
