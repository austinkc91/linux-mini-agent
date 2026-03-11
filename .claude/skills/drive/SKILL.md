---
name: drive
description: Terminal automation CLI for AI agents. Use drive to create tmux sessions, execute commands, send keystrokes, read output, poll for patterns, run commands in parallel across sessions, and manage processes. Always use --json for structured output.
---

# Drive — Terminal Automation via tmux

Run from: `cd apps/drive && uv run python main.py <command>`

Drive gives you full programmatic control over tmux sessions — creating terminals, running commands, reading output, and orchestrating parallel workloads.

## Commands

### session — Manage tmux sessions

```bash
drive session create agent-1 --json                     # Opens a terminal window (headed — default)
drive session create agent-1 --detach --json             # Headless (no terminal window)
drive session list --json                                # List all sessions
drive session kill agent-1 --json                        # Kill a session
```

**Default is headed** — a new terminal window opens attached to the session so you can watch live. Only use `--detach` when you explicitly need a headless session.

### run — Execute command and wait for completion

Uses sentinel protocol (`__DONE_<token>:<exit_code>`) for reliable completion detection.

```bash
drive run agent-1 "npm test" --json                     # Run and wait
drive run agent-1 "make build" --timeout 120 --json     # Custom timeout
```

### send — Raw keystrokes (no completion waiting)

```bash
drive send agent-1 "vim file.txt" --json
drive send agent-1 ":wq" --json
drive send agent-1 "y" --no-enter --json
```

### logs — Capture pane output

```bash
drive logs agent-1 --json
drive logs agent-1 --lines 500 --json
```

### poll — Wait for pattern in output

```bash
drive poll agent-1 --until "BUILD SUCCESS" --json
drive poll agent-1 --until "ready" --timeout 60 --json
```

### fanout — Parallel execution

```bash
drive fanout "npm test" --targets agent-1,agent-2,agent-3 --json
```

### proc — Process management

```bash
drive proc list --json
drive proc list --name claude --json
drive proc kill 12345 --json
drive proc kill --name "claude" --json
drive proc kill 12345 --tree --json
drive proc tree 12345 --json
drive proc top --session job-abc123 --json
```

## Key Patterns

- **Create sessions first** — `drive session create` before running commands
- **Use `run` for commands that complete** — It waits and gives you exit code + output
- **Use `send` for interactive tools** — vim, ipython, anything that doesn't "finish"
- **Use `poll` to wait for async events** — Watch for build completion, server startup, etc.
- **Use `logs` to inspect** — Check what happened in a pane
- **Use `fanout` for parallel work** — Run same command across multiple sessions
- **Use `proc` for process management** — List, kill, and inspect processes
- **Use `--json` always** — Structured output for reliable parsing
- **Write all files to /tmp** — Never write output files into the project directory

## Sentinel Protocol

Drive wraps commands with markers: `echo "__START_<token>" ; <cmd> ; echo "__DONE_<token>:$?"`
