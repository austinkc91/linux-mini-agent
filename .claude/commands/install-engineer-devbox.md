---
model: opus
description: Install and verify the engineer's device for sending jobs to the agent sandbox
argument-hint: [sandbox-ip-or-hostname]
---

# Purpose

Set up the engineer's device to send jobs to the remote agent sandbox. Installs minimal dependencies, configures the sandbox URL, verifies connectivity, and confirms the full pipeline works.

## Variables

SANDBOX_HOST: $ARGUMENTS
LISTEN_PORT: 7600

## Instructions

- This device only needs the CLI client tools — it does NOT need steer, xdotool, or tmux
- Use `apt` for system packages, `uv` for Python
- If SANDBOX_HOST is not provided, ask the user

## Workflow

### Phase 1: Install

1. Install uv and just if missing
2. Verify direct CLI: `cd apps/direct && uv run python main.py --help`

### Phase 2: Configure

3. Set AGENT_SANDBOX_URL in .env to `http://SANDBOX_HOST:7600`

### Phase 3: Verify

4. **Direct CLI**: `cd apps/direct && uv run python main.py --help`
5. **Justfile**: `just --list`
6. **Network ping**: `ping -c 1 -W 2 SANDBOX_HOST`
7. **Listen server**: `curl -s -m 5 http://SANDBOX_HOST:7600/jobs`
8. **SSH** (optional): `ssh -o ConnectTimeout=3 SANDBOX_HOST echo "ssh-ok"`
9. **End-to-end**: Submit a test job and verify it was accepted

## Report

| Check | Result |
|-------|--------|
| direct --help | [PASS/FAIL] |
| just --list | [PASS/FAIL] |
| ping sandbox | [PASS/FAIL] |
| listen server | [PASS/FAIL] |
| SSH (optional) | [PASS/FAIL/SKIP] |
| end-to-end job | [PASS/FAIL/SKIP] |

**[X/6 checks passed]** — [READY / NOT READY]

If ready: "Send jobs with `just send \"your prompt\"` or via Telegram bot."
