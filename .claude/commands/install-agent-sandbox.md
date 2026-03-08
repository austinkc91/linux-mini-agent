---
model: opus
description: Install, configure, and verify the steer agent sandbox on this macOS device
---

# Purpose

Run directly on the agent sandbox device (e.g. Mac Mini) to install all dependencies, clone the repo, build steer, set up Python environments, and run a full verification suite that proves the sandbox is operational. This is the local bootstrap — run it on the machine that will execute agent jobs.

## Variables

LISTEN_PORT: 7600

## Codebase Structure

```
steer/
├── apps/
│   ├── steer/          # Swift CLI — needs swift build -c release
│   ├── drive/          # Python CLI — needs uv
│   ├── listen/         # Python — needs uv (FastAPI server)
│   └── direct/         # Python — needs uv (CLI client)
├── .claude/
│   ├── commands/       # Slash commands
│   ├── skills/         # Agent skills (steer, drive)
│   └── agents/         # System prompts
└── justfile            # Task runner recipes
```

## Manual Prerequisites

Before running this installer, the user **must** grant the following permissions manually through System Settings. These cannot be automated.

| Permission | Why | How |
|------------|-----|-----|
| **Accessibility** | Steer needs to click, type, and read UI elements | System Settings > Privacy & Security > Accessibility > add Terminal |
| **Screen Recording** | Steer needs to capture screenshots (`steer see`) | System Settings > Privacy & Security > Screen Recording > add Terminal |
| **Full Disk Access** | Required for `systemsetup` and broad file access | System Settings > Privacy & Security > Full Disk Access > add Terminal |
| **Remote Login (SSH)** | Lets the engineer manage the sandbox remotely | System Settings > General > Sharing > toggle Remote Login on |

### Prevent Sleep (Keep-Alive)

The agent sandbox must never sleep — it needs to be always-on to pick up jobs at any time. A sleeping Mac won't respond to HTTP requests from Direct, and any in-progress jobs will stall. Run these commands to disable all sleep modes and enable automatic restart after power loss:

```bash
sudo pmset -a sleep 0 displaysleep 0 disksleep 0 standby 0 autopoweroff 0
sudo pmset -a autorestart 1
```

| Setting | What it prevents |
|---------|-----------------|
| `sleep 0` | System sleep — keeps the CPU and network active |
| `displaysleep 0` | Display sleep — prevents the GPU from powering down (needed for screenshots/OCR) |
| `disksleep 0` | Disk sleep — keeps storage responsive for job YAML reads/writes |
| `standby 0` | Standby mode — prevents deep hibernation after prolonged idle |
| `autopoweroff 0` | Auto power off — prevents macOS from shutting down after extended standby |
| `autorestart 1` | Auto restart — brings the Mac back up automatically after a power failure |

Verify the settings took effect with `pmset -g` — all sleep values should show `0` and `autorestart` should show `1`.

**Before starting the workflow**, ask the user: "Have you granted Accessibility, Screen Recording, and Full Disk Access to Terminal in System Settings, and applied the sleep prevention settings above? The verification checks will fail without these."

If the user says no or is unsure, show them the tables above and wait for confirmation before proceeding.

## Instructions

- All commands run locally via Bash — this is running ON the agent device
- Run each command individually so you can check the output before proceeding
- If a dependency is already installed, skip it and note the version
- If a step fails, stop and report the failure — do not continue blindly
- Do NOT install Xcode.app — only Xcode Command Line Tools are needed
- Do NOT attempt to modify macOS permissions via CLI — they must be granted manually (see Manual Prerequisites above)
- Use `brew` for all package installations
- Use `uv` for all Python dependency management — do NOT use pip
- Build steer in release mode: `swift build -c release`
- Verify each tool works after installation by running its `--version` or `--help`
- The verification phase must test real functionality, not just that binaries exist
- Every verification check must produce a clear PASS or FAIL result

## Workflow

### Phase 1: Install

1. Check macOS version:
   ```
   sw_vers
   ```

2. Check what's already installed — run `which` for each tool and capture versions:
   ```
   which brew swift tmux just uv yq claude node pi ipi
   ```
   Then for each found tool, run its version command:
   - `brew --version`
   - `swift --version`
   - `tmux -V`
   - `just --version`
   - `uv --version`
   - `yq --version`
   - `claude --version`
   - `node --version`
   - `pi --version` (optional — Pi Agent framework)

3. Install Xcode Command Line Tools if Swift is missing:
   ```
   xcode-select --install
   ```
   If already installed, skip.

4. Install Homebrew if missing:
   ```
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   ```
   If already installed, skip.

5. Install missing tools via Homebrew — only install what's missing:
   ```
   brew install tmux just uv yq
   ```

6. Install Node.js if missing:
   ```
   brew install node
   ```

7. Install Claude Code if missing:
   ```
   npm install -g @anthropic-ai/claude-code
   ```

8. Build steer (Swift CLI):
   ```
   cd apps/steer && swift build -c release 2>&1 | tail -5
   ```

9. Verify Python apps — uv will auto-install deps on first run:
    ```
    cd apps/drive && uv run python main.py --version
    cd apps/listen && uv run python main.py --help 2>&1 | head -1
    cd apps/direct && uv run python main.py --help 2>&1 | head -1
    ```

### Phase 2: Verify

Run each check and record PASS/FAIL. Do not stop on failure — run all checks and report results at the end.

10. **Steer binary** — confirm it runs and prints version:
    ```
    apps/steer/.build/release/steer --version
    ```

11. **Steer screenshots** — take a screenshot of the desktop (tests Screen Recording permission):
    ```
    apps/steer/.build/release/steer see --json
    ```
    PASS if JSON output contains a `screenshot` path to a valid PNG. FAIL if error or permission denied.

12. **Steer OCR** — run OCR on whatever is on screen (tests Vision framework):
    ```
    apps/steer/.build/release/steer ocr --json
    ```
    PASS if JSON output contains `elements` array. FAIL if error.

13. **Steer apps** — list running applications (tests Accessibility):
    ```
    apps/steer/.build/release/steer apps --json
    ```
    PASS if JSON output is an array with at least one app. FAIL if empty or error.

14. **Drive session** — create and destroy a tmux session (tests tmux):
    ```
    cd apps/drive && uv run python main.py session create --name verify-test --json
    cd apps/drive && uv run python main.py session list --json
    cd apps/drive && uv run python main.py session kill verify-test --json
    ```
    PASS if session creates, appears in list, and kills cleanly. FAIL if any step errors.

15. **Drive run** — execute a command in a tmux session (tests sentinel protocol):
    ```
    cd apps/drive && uv run python main.py session create --name verify-run --json
    cd apps/drive && uv run python main.py run verify-run "echo hello-from-drive" --json
    cd apps/drive && uv run python main.py session kill verify-run --json
    ```
    PASS if run output contains "hello-from-drive" and exit code 0. FAIL otherwise.

16. **Listen server** — start listen, verify it responds, then stop it:
    ```
    cd apps/listen && uv run python main.py &
    LISTEN_PID=$!
    sleep 2
    curl -s http://localhost:7600/jobs
    kill $LISTEN_PID 2>/dev/null
    ```
    PASS if curl returns a YAML response. FAIL if connection refused or error.

17. **Direct client** — verify the CLI parses correctly:
    ```
    cd apps/direct && uv run python main.py --help
    ```
    PASS if help text shows start/get/list/stop commands. FAIL if error.

18. **Justfile** — verify all recipes are visible:
    ```
    just --list
    ```
    PASS if output includes listen, send, job, jobs, stop. FAIL if any are missing.

19. **Claude Code** — verify it can start (non-interactive):
    ```
    claude --version
    ```
    PASS if version string returned. FAIL if command not found.

20. Remind the user about manual macOS permissions if any steer checks failed:

    | Permission | Why | How |
    |------------|-----|-----|
    | **Accessibility** | steer click, type, hotkey, drag, apps | System Settings > Privacy & Security > Accessibility > add Terminal |
    | **Screen Recording** | steer see, ocr | System Settings > Privacy & Security > Screen Recording > add Terminal |
    | **Full Disk Access** | systemsetup, broad file access | System Settings > Privacy & Security > Full Disk Access > add Terminal |
    | **Remote Login (SSH)** | Manage sandbox remotely | System Settings > General > Sharing > toggle Remote Login on |

21. Now follow the `Report` section to report the completed work

## Report

Present results in this format:

## Agent Sandbox: [hostname]

**macOS**: [version]
**Repo**: [path]

### Dependencies

| Tool | Status | Version |
|------|--------|---------|
| Xcode CLI Tools | [installed/missing] | [version] |
| Homebrew | [installed/missing] | [version] |
| Swift | [installed/missing] | [version] |
| tmux | [installed/missing] | [version] |
| just | [installed/missing] | [version] |
| uv | [installed/missing] | [version] |
| yq | [installed/missing] | [version] |
| Node.js | [installed/missing] | [version] |
| Claude Code | [installed/missing] | [version] |
| Pi Agent (optional) | [installed/not installed] | [version] |

### Apps

| App | Build | Notes |
|-----|-------|-------|
| steer | [built/failed] | [binary path or error] |
| drive | [ready/failed] | [version or error] |
| listen | [ready/failed] | [notes] |
| direct | [ready/failed] | [notes] |

### Verification

| Check | Result | Details |
|-------|--------|---------|
| steer --version | [PASS/FAIL] | [version or error] |
| steer see (screenshot) | [PASS/FAIL] | [screenshot path or error] |
| steer ocr | [PASS/FAIL] | [element count or error] |
| steer apps | [PASS/FAIL] | [app count or error] |
| drive session create/kill | [PASS/FAIL] | [details] |
| drive run (sentinel) | [PASS/FAIL] | [output or error] |
| listen server | [PASS/FAIL] | [response or error] |
| direct --help | [PASS/FAIL] | [commands found or error] |
| just --list | [PASS/FAIL] | [recipe count or error] |
| claude --version | [PASS/FAIL] | [version or error] |

### Permissions

If any steer checks failed, list which permissions need to be granted:

| Permission | How |
|------------|-----|
| Accessibility | System Settings > Privacy & Security > Accessibility > add Terminal |
| Screen Recording | System Settings > Privacy & Security > Screen Recording > add Terminal |
| Full Disk Access | System Settings > Privacy & Security > Full Disk Access > add Terminal |
| Remote Login (SSH) | System Settings > General > Sharing > toggle Remote Login on |

### Result

**[X/10 checks passed]** — [READY / NOT READY — needs attention]

If all 10 pass: "Sandbox is fully operational. Start the server with `just listen`."
If any fail: List what needs to be fixed before the sandbox is ready.

### Fix It?

If any dependencies are missing or any checks failed (excluding macOS permissions which require manual setup), ask the user:

> "Would you like me to install the missing pieces and re-run the failed checks?"

If they say yes, go back and install/fix only what failed, then re-run only the failed verification checks and present an updated report.
