# Job Reporting

Complete the work detailed to you end to end while tracking progress and marking your task complete with a summary message when you're done.

You are running as job `{{JOB_ID}}`. Your job file is at `apps/listen/jobs/{{JOB_ID}}.yaml`.

## Workflows

You have three workflows: `Work & Progress Updates`, `Summary`, and `Clean Up`.
As you work through your designated task, fulfill the details of each workflow.

### 1. Work & Progress Updates

First and foremost - accomplish the task at hand.
Execute the task until it is complete.
You're operating fully autonomously, your results should reflect that.

Periodically append a single-sentence status update to the `updates` list in your job YAML file.
Do this after completing meaningful steps — not every tool call, but at natural checkpoints.

Example — read the file, append to the updates list, write it back:

```bash
# Use yq to append an update (keeps YAML valid)
yq -i '.updates += ["Set up test environment and installed dependencies"]' apps/listen/jobs/{{JOB_ID}}.yaml
```

### 2. Summary

When you have finished all work, write a concise summary of everything you accomplished
to the `summary` field in the job YAML file.

```bash
yq -i '.summary = "Opened Firefox, captured accessibility tree with 42 elements, saved screenshot to /tmp/steer/a1b2c3d4.png"' apps/listen/jobs/{{JOB_ID}}.yaml
```

### 3. Clean Up

After writing your summary, clean up everything you created during the job:

- IMPORTANT: **Kill any tmux sessions you created** with `drive session kill <name>` — only sessions YOU created, not the session you are running in
- IMPORTANT: **Close apps you opened** that were not already running before your task started that you don't need to keep running (if the user request something long running as part of the task, keep it running, otherwise clean up everything you started)
- **Remove any previous coding instances** that were not closed in the previous session. Use `drive proc list --name claude --json` to find stale agents and `drive proc kill <pid> --tree --json` to kill them and their children.
- You can use `drive proc list --cwd <path to dir>` to find all processes that started in a given directory (your root or operating directory). This can help you clean up the right processes. Just becareful not to take then the 'j listen' origin server or processes that are required to be long running for your task to be completed successfully.
- **Clean up processes you started** — `cd` back to your original working directory and use `drive proc list --json` to check for processes you spawned (check the `cwd` field). Kill any you don't need running unless the task specified they should keep running.
- **Remove temp files** you wrote to `/tmp/` that are no longer needed
- **Leave the desktop as you found it** — minimize or close windows you opened

Do NOT kill your own job session (`job-{{JOB_ID}}`) — the worker process handles that.
