---
model: opus
description: Install and verify the engineer's primary device for sending jobs to the agent sandbox
argument-hint: [sandbox-ip-or-hostname]
---

# Purpose

Set up the engineer's primary device (e.g. MacBook Pro) to send jobs to the remote agent sandbox. Installs minimal dependencies, configures the sandbox URL, verifies connectivity, and confirms the full direct-to-listen pipeline works end-to-end.

## Variables

SANDBOX_HOST: $ARGUMENTS
LISTEN_PORT: 7600

## Instructions

- All commands run locally on the engineer's machine — this is the PRIMARY device, not the sandbox
- This device only needs the CLI client tools — it does NOT need steer, Swift, or tmux
- If a dependency is already installed, skip it and note the version
- If a step fails, stop and report the failure — do not continue blindly
- Use `brew` for all package installations
- Use `uv` for all Python dependency management — do NOT use pip
- If SANDBOX_HOST is not provided, ask the user for the Mac Mini's IP or hostname
- The justfile `url` variable should point to `http://SANDBOX_HOST:LISTEN_PORT`
- Do NOT modify the sandbox device — only configure this local machine
- SSH connectivity is optional but recommended for debugging

## Workflow

### Phase 1: Install

1. Check macOS version:
   ```
   sw_vers
   ```

2. Check what's already installed:
   ```
   which brew uv just git ssh
   ```
   Then for each found tool, run its version command:
   - `brew --version`
   - `uv --version`
   - `just --version`
   - `git --version`

3. Install Homebrew if missing:
   ```
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   ```
   If already installed, skip.

4. Install missing tools via Homebrew — only install what's missing:
   ```
   brew install uv just
   ```

5. Verify the repo exists. If this command is being run from the repo, note the current path. If the repo isn't cloned yet, ask the user for the clone URL.

6. Verify Python apps for the client side — uv will auto-install deps on first run:
   ```
   cd apps/direct && uv run python main.py --help 2>&1 | head -5
   ```

### Phase 2: Configure

7. Read the current justfile URL:
   ```
   head -3 justfile
   ```

8. If the `url` variable in justfile doesn't match `http://SANDBOX_HOST:LISTEN_PORT`, update it. Ask the user to confirm before modifying.

### Phase 3: Verify

Run each check and record PASS/FAIL. Do not stop on failure — run all checks and report results at the end.

9. **Direct CLI** — verify the client parses correctly:
    ```
    cd apps/direct && uv run python main.py --help
    ```
    PASS if help text shows start/get/list/stop commands. FAIL if error.

10. **Justfile** — verify all recipes are visible:
    ```
    just --list
    ```
    PASS if output includes listen, send, job, jobs, stop. FAIL if any are missing.

11. **Network ping** — verify the sandbox device is reachable:
    ```
    ping -c 1 -W 2 SANDBOX_HOST
    ```
    PASS if ping succeeds. FAIL if host unreachable.

12. **Listen server** — verify the sandbox's listen server is responding:
    ```
    curl -s -m 5 http://SANDBOX_HOST:7600/jobs
    ```
    PASS if returns a YAML response. FAIL if connection refused or timeout. If FAIL, note that the sandbox may need `just listen` started.

13. **SSH connectivity** (optional) — test SSH access to the sandbox:
    ```
    ssh -o ConnectTimeout=3 -o BatchMode=yes SANDBOX_HOST echo "ssh-ok" 2>&1
    ```
    PASS if "ssh-ok" returned. FAIL/SKIP if refused or timeout — note this is optional.

14. **End-to-end test** — if listen server is running (check 12 passed), send a test job and verify it was accepted:
    ```
    cd apps/direct && uv run python main.py start http://SANDBOX_HOST:7600 "echo test from devbox"
    ```
    PASS if a job ID is returned. FAIL if error. If PASS, immediately check the job:
    ```
    cd apps/direct && uv run python main.py get http://SANDBOX_HOST:7600 JOB_ID
    ```
    PASS if job YAML returned with status running or completed.

15. Now follow the `Report` section to report the completed work

## Report

Present results in this format:

## Engineer Devbox: [hostname]

**macOS**: [version]
**Repo**: [path]
**Sandbox target**: [SANDBOX_HOST:LISTEN_PORT]

### Dependencies

| Tool | Status | Version |
|------|--------|---------|
| Homebrew | [installed/missing] | [version] |
| uv | [installed/missing] | [version] |
| just | [installed/missing] | [version] |
| git | [installed/missing] | [version] |

### Verification

| Check | Result | Details |
|-------|--------|---------|
| direct --help | [PASS/FAIL] | [commands found or error] |
| just --list | [PASS/FAIL] | [recipe count or error] |
| ping sandbox | [PASS/FAIL] | [latency or error] |
| listen server | [PASS/FAIL] | [response or "not running"] |
| SSH (optional) | [PASS/FAIL/SKIP] | [details] |
| end-to-end job | [PASS/FAIL/SKIP] | [job ID or error] |

### Result

**[X/6 checks passed]** — [READY / NOT READY — needs attention]

If all pass: "Devbox is ready. Send jobs with `just send \"your prompt\"`."
If listen server failed: "Sandbox listen server not running. Start it on the Mac Mini with `just listen`."
If other failures: List what needs to be fixed.

### Fix It?

If any dependencies are missing or checks failed, ask the user:

> "Would you like me to install the missing pieces and re-run the failed checks?"

If they say yes, go back and install/fix only what failed, then re-run only the failed verification checks and present an updated report.
