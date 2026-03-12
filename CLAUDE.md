# Linux Mini Agent

Linux desktop automation for AI agents. Five Python apps that give agents full GUI + terminal control, with remote access via Telegram.

## Architecture

```
linux-mini-agent/
├── apps/
│   ├── steer/      — GUI automation (xdotool, scrot, tesseract, wmctrl, xclip)
│   ├── drive/      — Terminal automation (tmux sessions, commands, output)
│   ├── listen/     — Job server (FastAPI on port 7600)
│   ├── direct/     — CLI client for Listen
│   └── telegram/   — Telegram bot for remote control from mobile
├── justfile        — Task runner (just listen, just send, just telegram, etc.)
├── install.sh      — Automated installer for Linux
├── install-services.sh — Systemd service installer (auto-start on boot)
└── systemd/        — Service unit files for listen + telegram
```

## Setup

Run the installer to set up everything on a Linux machine:

```bash
./install.sh
```

Or install manually:

```bash
# System dependencies
sudo apt update
sudo apt install -y tmux xdotool scrot tesseract-ocr wmctrl xclip \
    x11-utils imagemagick python3-gi gir1.2-atspi-2.0

# uv (Python package manager) — required
curl -LsSf https://astral.sh/uv/install.sh | sh

# just (task runner) — required
sudo apt install -y just || cargo install just

# Sync all Python app dependencies
cd apps/steer && uv sync && cd ../..
cd apps/drive && uv sync && cd ../..
cd apps/listen && uv sync && cd ../..
cd apps/direct && uv sync && cd ../..
cd apps/telegram && uv sync && cd ../..
```

## Running

```bash
# Verify installation
just install-check

# Start the job server
just listen

# Start Telegram bot (needs TELEGRAM_BOT_TOKEN in .env)
just telegram

# Send a job
just send "Open Firefox and navigate to github.com"

# GUI automation
cd apps/steer && uv run python main.py see --json
cd apps/steer && uv run python main.py click -x 500 -y 300
cd apps/steer && uv run python main.py ocr --store --json

# Terminal automation
cd apps/drive && uv run python main.py session create my-session --detach --json
cd apps/drive && uv run python main.py run my-session "echo hello" --json
```

## Apps

### steer — GUI Automation
`cd apps/steer && uv run python main.py <command> --json`

14 commands: `see`, `click`, `type`, `hotkey`, `scroll`, `drag`, `apps`, `screens`, `window`, `ocr`, `focus`, `find`, `clipboard`, `wait`

Depends on: xdotool, scrot, tesseract-ocr, wmctrl, xclip, xrandr, imagemagick
Optional: python3-gi + gir1.2-atspi-2.0 (for AT-SPI accessibility trees)

### drive — Terminal Automation
`cd apps/drive && uv run python main.py <command> --json`

7 commands: `session`, `run`, `send`, `logs`, `poll`, `fanout`, `proc`

Depends on: tmux

### listen — Job Server
`cd apps/listen && uv run python main.py`

FastAPI server on port 7600. Endpoints: POST /job, GET /job/{id}, GET /jobs, DELETE /job/{id}, POST /cron, GET /crons, GET /cron/{id}, PUT /cron/{id}, DELETE /cron/{id}, POST /cron/{id}/trigger

Includes persistent cron scheduler (APScheduler) — cron definitions stored in `crons.yaml`, loaded on startup, survive reboots.

### direct — CLI Client
`cd apps/direct && uv run python main.py <command>`

Commands: start, get, list, latest, stop, clear

### telegram — Remote Control Bot
`cd apps/telegram && uv run python main.py`

Requires: `TELEGRAM_BOT_TOKEN` env var. Optional: `TELEGRAM_ALLOWED_USERS` (comma-separated user IDs for security).

Commands via Telegram: /job, /jobs, /status, /stop, /screenshot, /steer, /drive, /shell, /cron. Plain text messages auto-submit as jobs. Send photos/files to save them for agent use.

Cron management via `/cron`:
- `/cron list` — show all scheduled crons
- `/cron add <crontab> | <name> | <prompt>` — create a persistent cron
- `/cron del <id>` — delete a cron
- `/cron toggle <id>` — enable/disable
- `/cron edit <id> schedule|name|prompt <value>` — edit a field
- `/cron trigger <id>` — fire immediately for testing

## Auto-Start on Boot

Install systemd services so listen + telegram survive reboots:

```bash
sudo ./install-services.sh    # or: just install-services
```

This registers two systemd services:
- `linux-agent-listen` — job server (always enabled)
- `linux-agent-telegram` — telegram bot (enabled only if TELEGRAM_BOT_TOKEN is set)

```bash
# Manual control
just start-services      # start both now
just stop-services       # stop both
just service-status      # check status
just service-logs        # tail live logs

# Or use systemctl directly
sudo systemctl status linux-agent-listen
journalctl -u linux-agent-telegram -f
```

## Key Patterns

- **Observe-Act-Verify**: `steer see` → action → `steer see` again
- **Sentinel Protocol**: Drive wraps commands with `__DONE_<token>:<exit_code>` markers
- **Element IDs**: B=button, T=text, S=static, O=OCR, etc. Valid within a snapshot only
- **JSON mode**: Always pass `--json` for structured output
- **One steer command per bash call**: Screen changes after every action

## Environment Variables

Copy `.env.sample` to `.env` and fill in:

| Variable | Required | Purpose |
|----------|----------|---------|
| `ANTHROPIC_API_KEY` | For Claude | Claude Code API key |
| `TELEGRAM_BOT_TOKEN` | For Telegram | From @BotFather |
| `TELEGRAM_ALLOWED_USERS` | Recommended | Comma-separated Telegram user IDs |
| `LISTEN_URL` | Optional | Listen server URL (default: http://localhost:7600) |
| `AGENT_SANDBOX_URL` | Optional | Remote sandbox URL for direct client |

## System Requirements

- **Linux** with X11 display (Wayland not supported)
- **Python 3.11+**
- **uv** (Python package manager)
- **tmux** (terminal multiplexer)
- **xdotool** (mouse/keyboard/window control)
- **scrot** (screenshots)
- **tesseract-ocr** (OCR)
- **wmctrl** (window management)
- **xclip** (clipboard)
- **just** (task runner)
