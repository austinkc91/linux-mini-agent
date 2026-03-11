---
model: opus
description: Install, configure, and verify the Linux agent sandbox on this device
---

# Purpose

Run directly on the agent sandbox device (Linux desktop) to install all dependencies, set up Python environments, and run a full verification suite that proves the sandbox is operational.

## Variables

LISTEN_PORT: 7600

## Codebase Structure

```
linux-mini-agent/
├── apps/
│   ├── steer/          # Python CLI — needs xdotool, scrot, tesseract, wmctrl, xclip
│   ├── drive/          # Python CLI — needs tmux, uv
│   ├── listen/         # Python — needs uv (FastAPI server)
│   ├── direct/         # Python — needs uv (CLI client)
│   └── telegram/       # Python — Telegram bot (optional)
├── .claude/
│   ├── commands/       # Slash commands
│   ├── skills/         # Agent skills (steer, drive)
│   └── agents/         # System prompts
└── justfile            # Task runner recipes
```

## Prerequisites

- Linux desktop with X11 display
- sudo access for installing packages

## Instructions

- All commands run locally via Bash — this is running ON the agent device
- Run each command individually so you can check the output before proceeding
- If a step fails, stop and report the failure — do not continue blindly
- Use `apt` for system package installations (adjust for your distro)
- Use `uv` for all Python dependency management — do NOT use pip
- Verify each tool works after installation
- The verification phase must test real functionality, not just that binaries exist

## Workflow

### Phase 1: Install

1. Check Linux version:
   ```
   cat /etc/os-release
   uname -a
   ```

2. Check what's already installed:
   ```
   which tmux xdotool scrot tesseract wmctrl xclip xrandr uv just claude node
   ```

3. Install system dependencies:
   ```
   sudo apt update
   sudo apt install -y tmux xdotool scrot tesseract-ocr wmctrl xclip \
       x11-utils imagemagick python3-gi gir1.2-atspi-2.0
   ```

4. Install uv if missing:
   ```
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

5. Install just if missing:
   ```
   sudo apt install -y just
   ```

6. Install Node.js if missing:
   ```
   sudo apt install -y nodejs npm
   ```

7. Install Claude Code if missing:
   ```
   npm install -g @anthropic-ai/claude-code
   ```

8. Verify Python apps:
   ```
   cd apps/steer && uv run python main.py --version
   cd apps/drive && uv run python main.py --version
   cd apps/listen && uv run python main.py --help 2>&1 | head -1
   cd apps/direct && uv run python main.py --help 2>&1 | head -1
   ```

### Phase 2: Verify

Run each check and record PASS/FAIL.

9. **Steer version**: `cd apps/steer && uv run python main.py --version`

10. **Steer screenshots**: `cd apps/steer && uv run python main.py see --json`

11. **Steer OCR**: `cd apps/steer && uv run python main.py ocr --json`

12. **Steer apps**: `cd apps/steer && uv run python main.py apps --json`

13. **Drive session**: create/list/kill tmux session

14. **Drive run**: execute command with sentinel protocol

15. **Listen server**: start, curl, stop

16. **Direct client**: `--help`

17. **Justfile**: `just --list`

18. **Claude Code**: `claude --version`

### Phase 3: Prevent Sleep (Optional)

For always-on agent, prevent screen blanking:
```bash
xset s off && xset -dpms && xset s noblank
```

## Report

| Check | Result | Details |
|-------|--------|---------|
| steer --version | [PASS/FAIL] | |
| steer see | [PASS/FAIL] | |
| steer ocr | [PASS/FAIL] | |
| steer apps | [PASS/FAIL] | |
| drive session | [PASS/FAIL] | |
| drive run | [PASS/FAIL] | |
| listen server | [PASS/FAIL] | |
| direct --help | [PASS/FAIL] | |
| just --list | [PASS/FAIL] | |
| claude --version | [PASS/FAIL] | |

**[X/10 checks passed]** — [READY / NOT READY]
