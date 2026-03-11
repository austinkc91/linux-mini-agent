# Linux Mini Agent

**Linux desktop automation for AI agents. Direct your agents to steer, drive, listen, and control your machine remotely via Telegram.**

Engineers are already using AI agents to write code — but those agents are trapped inside the terminal. This is the missing layer between "agent writes code" and "agent ships features." It gives AI agents full control of your Linux desktop: clicking buttons, reading screens via OCR, typing into any app, and orchestrating terminals via tmux. Control it all remotely from your phone via Telegram.

---

## The Problem

AI agents can write code, plan, and reason. But they can't open an app. They can't click a button. They can't read what's on your screen. There's a massive gap between an agent that writes code and an agent that ships features.

That gap is **computer use**. And for Linux desktop automation, the existing tools fall short:

- **Accessibility trees return nothing** for Electron apps (VS Code, Slack, Notion)
- **Terminal agents** can run commands but can't see output, recover from errors, or coordinate with GUI tools
- **No orchestration layer** exists to combine terminal control with GUI automation
- **No remote control** — you can't direct your agent from your phone

The Linux Mini Agent solves this with five purpose-built CLIs.

## The Solution

Two Skills, Five CLIs. Full agent autonomy. **Telegram is the primary user interface** — you chat with your agent from your phone just like texting a person. Send it tasks, get screenshots back, upload files, and monitor progress — all from the Telegram app on any device.

---

## How It Works

```
You (phone/desktop)          Linux Machine
┌──────────────┐       ┌─────────────────────────┐
│              │       │  Telegram Bot            │
│  Telegram    │◄─────►│    ↕                     │
│  App         │       │  Listen Server (jobs)    │
│              │       │    ↕                     │
└──────────────┘       │  Claude Code Agent       │
                       │    ↕              ↕      │
                       │  Drive (terminal) Steer  │
                       │                  (GUI)   │
                       └─────────────────────────┘
```

1. **You message your Telegram bot** with a task (text, photo, or file)
2. **Listen server** queues the job and spawns a Claude Code agent
3. **The agent uses Steer** (GUI automation) and **Drive** (terminal control) to complete the task
4. **You get updates back in Telegram** — screenshots, status, results

---

## Apps

### Telegram — Chat Interface (Primary)

> **Your main way to interact with the agent.** Chat with it like texting — send tasks, get screenshots, upload files.

**Python** · v0.1.0 · python-telegram-bot

Telegram is the user-facing interface. You talk to your agent through it — send prompts as plain text messages, upload images and files for context, get screenshots back, and monitor job progress. It connects to the Listen server which orchestrates everything.

| Action         | What happens                               |
| -------------- | ------------------------------------------ |
| Send text      | Automatically submitted as a job prompt    |
| Send photo     | Saved for agent use, acknowledged          |
| Send file      | Saved for agent use, acknowledged          |
| `/screenshot`  | Takes a screenshot and sends it back       |
| `/jobs`        | Lists all jobs and their status            |
| `/status <id>` | Shows detailed progress for a job          |
| `/stop <id>`   | Stops a running job                        |
| `/steer <cmd>` | Runs a GUI automation command directly     |
| `/drive <cmd>` | Runs a terminal command directly           |
| `/shell <cmd>` | Runs an arbitrary shell command            |

---

### Steer — GUI Control

> Linux GUI automation CLI for AI agents. Eyes and hands on your desktop.

**Python** · v0.2.0 · 14 commands · xdotool + scrot + tesseract + wmctrl

Steer gives agents the ability to see, interact with, and control any Linux application through screenshots, OCR, accessibility trees (AT-SPI), and input simulation.

| Command     | Purpose                                             |
| ----------- | --------------------------------------------------- |
| `see`       | Capture screenshots of apps, windows, or screens    |
| `click`     | Click at coordinates or on detected text elements   |
| `type`      | Type text into any focused application              |
| `hotkey`    | Send keyboard shortcuts (ctrl+s, alt+tab, etc.)     |
| `scroll`    | Scroll in any direction within an app               |
| `drag`      | Drag from one point to another                      |
| `apps`      | List running applications                           |
| `screens`   | List available displays                             |
| `window`    | Move, resize, and manage windows                    |
| `ocr`       | Extract text from screen via Tesseract OCR          |
| `focus`     | Show currently focused element                      |
| `find`      | Locate UI elements on screen                        |
| `clipboard` | Read and write the system clipboard                 |
| `wait`      | Wait for conditions (element visible, text appears) |

#### OCR: The Equalizer

Electron apps (VS Code, Slack, Notion) return **completely empty accessibility trees**. Every AI agent trying to interact with these apps is flying blind — unless you use OCR.

One command — `steer ocr --store` — and suddenly every piece of text on screen becomes a clickable, addressable element.

---

### Drive — Terminal Control

> Terminal automation CLI for AI agents. Programmatic tmux control.

**Python** · v0.1.0 · 7 commands

| Command   | Purpose                                                  |
| --------- | -------------------------------------------------------- |
| `session` | Create, list, and manage tmux sessions                   |
| `run`     | Execute a command in a tmux pane and wait for completion |
| `send`    | Send keystrokes to a tmux pane                           |
| `logs`    | Capture pane output (capture-pane)                       |
| `poll`    | Wait for a sentinel marker indicating command completion |
| `fanout`  | Execute commands across multiple panes in parallel       |
| `proc`    | List, kill, and manage processes                         |

---

### Listen — Job Server

> HTTP server + job manager for remote agent execution.

**Python** · v0.1.0 · FastAPI

| Endpoint           | Purpose                                |
| ------------------ | -------------------------------------- |
| `POST /job`        | Submit a prompt, get back a job ID     |
| `GET /job/{id}`    | Check job status, updates, and summary |
| `GET /jobs`        | List all jobs                          |
| `DELETE /job/{id}` | Stop a running job                     |

```bash
just listen                    # Start server on port 7600
just send "Open Firefox..."   # Submit a job via Direct
just jobs                      # List all jobs
just job <id>                  # Check a specific job
```

---

### Direct — CLI Client

> CLI client for the Listen server. Alternative to Telegram for local/scripted use.

**Python** · v0.1.0 · httpx + Click

---

## Quick Start

```bash
# 1. Install everything
./install.sh

# 2. Edit .env with your API keys and Telegram bot token
nano .env

# 3. Start the agent (or install systemd services for auto-start)
just listen                  # Start job server (terminal 1)
just telegram                # Start Telegram bot (terminal 2)

# 4. Message your Telegram bot — just type a task and send!
```

Or install as system services so it runs on boot:

```bash
sudo ./install-services.sh   # Auto-starts on every reboot
```

---

## Project Structure

```
linux-mini-agent/
├── apps/
│   ├── steer/          # Python CLI — Linux GUI automation
│   │   ├── commands/   # 14 command implementations
│   │   └── modules/    # screen_capture, mouse, keyboard, ocr, accessibility
│   ├── drive/          # Python CLI — tmux terminal control
│   │   └── commands/   # 7 command implementations
│   ├── listen/         # Python — FastAPI job server
│   │   ├── jobs/       # YAML job state files
│   │   └── worker.py   # Agent spawner
│   ├── direct/         # Python — CLI client for Listen
│   └── telegram/       # Python — Telegram bot for remote control
└── assets/
    └── diagrams/
```

---

## Setup

### Agent Machine (Linux Desktop)

The agent machine needs Linux with an X11 display, tmux, and the GUI tools.

**System dependencies:**

```bash
# Core tools
sudo apt install tmux xdotool scrot tesseract-ocr wmctrl xclip x11-utils imagemagick

# Python + uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Task runner
sudo apt install just  # or: cargo install just

# Optional: AT-SPI accessibility
sudo apt install python3-gi gir1.2-atspi-2.0

# Claude Code
npm install -g @anthropic-ai/claude-code
```

**Verify:**

```bash
cd apps/steer && uv run python main.py --version
cd apps/drive && uv run python main.py --version
just listen  # Start server on port 7600
```

**Prevent sleep / screen blanking** (for always-on agent):

```bash
xset s off && xset -dpms && xset s noblank
```

### Telegram Bot Setup

1. Message **@BotFather** on Telegram
2. Send `/newbot` and follow prompts to create your bot
3. Copy the bot token
4. Configure and start:

```bash
export TELEGRAM_BOT_TOKEN='your-token-here'
export TELEGRAM_ALLOWED_USERS='your-telegram-user-id'  # Security!
export LISTEN_URL='http://localhost:7600'

just telegram
```

5. Message your bot to start controlling your agent from your phone!

### Auto-Start on Boot

Make the listen server and telegram bot survive reboots:

```bash
sudo ./install-services.sh    # or: just install-services
```

This installs two systemd services that auto-start on boot:
- `linux-agent-listen` — job server on port 7600
- `linux-agent-telegram` — telegram bot (only enabled if TELEGRAM_BOT_TOKEN is set)

```bash
just start-services      # start both now
just stop-services       # stop both
just service-status      # check status
just service-logs        # tail live logs
```

### Remote Client (CLI)

```bash
just send "Open Firefox and search for Python docs"
just jobs
just job <id>
just stop <id>
```

---

## Key Patterns

### Cross-App Pipelines

Combine Steer and Drive to build pipelines that span multiple applications.

### Agent-on-Agent Orchestration

One AI agent can control other AI agents through tmux.

### Telegram as Chat Interface

Telegram is the primary way users interact with the agent. Just message your bot — send a task as plain text, attach photos or files for context, and get results back. It's like texting your computer.

---

## Custom Agent Support

Steer and Drive are agent-agnostic tools. Any CLI-based AI agent can use them:

- **Claude Code** — Anthropic's CLI agent
- **Gemini CLI** — Google's CLI agent
- **Codex CLI** — OpenAI's CLI agent
- **OpenCode** — Open-source alternative

The agent just needs to be able to invoke shell commands. Steer and Drive handle the rest.
