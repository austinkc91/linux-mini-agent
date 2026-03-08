# Mac Mini Agent

**macOS automation for AI agents. Direct your agents to steer, drive and listen.**

<p align="center">
  <img src="assets/architecture-v3-animated.svg" alt="Steer Architecture" width="100%"/>
</p>

Engineers are already using AI agents to write code — but those agents are trapped inside the terminal. Steer is the missing layer between "agent writes code" and "agent ships features." It gives AI agents full control of your Mac: clicking buttons, reading screens via OCR, typing into any app, and orchestrating terminals via tmux.

---

## The Problem

AI agents can write code, plan, and reason. But they can't open an app. They can't click a button. They can't read what's on your screen. There's a massive gap between an agent that writes code and an agent that ships features.

That gap is **computer use**. And for macOS, the existing tools fall short:

- **Accessibility trees return nothing** for Electron apps (VS Code, Slack, Notion)
- **Terminal agents** can run commands but can't see output, recover from errors, or coordinate with GUI tools
- **No orchestration layer** exists to combine terminal control with GUI automation

The Mac Mini Agent solves this with four purpose-built CLIs.

## The Solution

> Soon, there will be more agents operating computers than engineers operating computers — but you can be the one who deploys and controls them.
>
> The Mac Mini Agent is a minimal toolkit you can adopt to deploy onto any of your [Mac devices](https://www.apple.com/newsroom/), to give AI agents the power to use your computer like you do.

**When you increase your agent's autonomy, you increase your own.** An agent that can only write code still needs you to test it, deploy it, and verify it. An agent that can see the screen, click buttons, orchestrate terminals, and operate across apps — that agent can ship while you sleep.

Two Skills, Four CLIs. Many Macs. Full agent autonomy.

---

## Who Is This For?

Mid-Senior+ engineers who want to move beyond terminal agent interactions into true computer-use agents that can operate autonomously across an entire environment.

If your agent can write code but can't ship it — Steer and Drive close that gap.

---

## Apps

### Steer — GUI Control

> macOS automation CLI for AI agents. Eyes and hands on your Mac.

**Swift** · v0.2.0 · 14 commands

Steer gives agents the ability to see, interact with, and control any macOS application through screenshots, OCR, accessibility trees, and input simulation.

<p align="center">
  <img src="assets/diagrams/steer-command-fan.svg" alt="Steer Commands" width="600"/>
</p>

| Command     | Purpose                                             |
| ----------- | --------------------------------------------------- |
| `see`       | Capture screenshots of apps, windows, or screens    |
| `click`     | Click at coordinates or on detected text elements   |
| `type`      | Type text into any focused application              |
| `hotkey`    | Send keyboard shortcuts (cmd+s, cmd+tab, etc.)      |
| `scroll`    | Scroll in any direction within an app               |
| `drag`      | Drag from one point to another                      |
| `apps`      | List running applications                           |
| `screens`   | List available displays                             |
| `window`    | Move, resize, and manage windows                    |
| `ocr`       | Extract text from screen via Vision framework       |
| `focus`     | Activate and focus a specific application           |
| `find`      | Locate UI elements on screen                        |
| `clipboard` | Read and write the system clipboard                 |
| `wait`      | Wait for conditions (element visible, text appears) |

#### OCR: The Equalizer

Electron apps (VS Code, Slack, Notion) return **completely empty accessibility trees**. Every AI agent trying to interact with these apps is flying blind — unless you use OCR.

<p align="center">
  <img src="assets/diagrams/ocr-equalizer.svg" alt="OCR Equalizer" width="700"/>
</p>

One command — `steer ocr --store` — and suddenly every piece of text on screen becomes a clickable, addressable element. This was the breakthrough that unlocked everything else.

---

### Drive — Terminal Control

> Terminal automation CLI for AI agents. Programmatic tmux control.

**Python** · v0.1.0 · 6 commands

Drive gives agents full programmatic control over tmux sessions — creating terminals, sending commands, reading output, and orchestrating parallel workloads.

<p align="center">
  <img src="assets/diagrams/drive-command-flow.svg" alt="Drive Command Flow" width="450"/>
</p>

| Command   | Purpose                                                  |
| --------- | -------------------------------------------------------- |
| `session` | Create, list, and manage tmux sessions                   |
| `run`     | Execute a command in a tmux pane and wait for completion |
| `send`    | Send keystrokes to a tmux pane                           |
| `logs`    | Capture pane output (capture-pane)                       |
| `poll`    | Wait for a sentinel marker indicating command completion |
| `fanout`  | Execute commands across multiple panes in parallel       |

#### The Sentinel Pattern

Drive uses a sentinel marker pattern (`__DONE_<token>:<exit_code>`) to reliably detect when commands complete in tmux sessions. This is what makes async terminal orchestration deterministic instead of guesswork.

<p align="center">
  <img src="assets/diagrams/sentinel-pattern.svg" alt="Sentinel Pattern" width="700"/>
</p>

---

### Listen — Job Server

> HTTP server + job manager for remote agent execution.

**Python** · v0.1.0 · FastAPI

Listen accepts job requests over HTTP, spawns Claude Code agents as worker processes, and tracks their progress via YAML job files. It's the dispatch layer that turns a prompt into a running agent.

| Endpoint           | Purpose                                |
| ------------------ | -------------------------------------- |
| `POST /job`        | Submit a prompt, get back a job ID     |
| `GET /job/{id}`    | Check job status, updates, and summary |
| `GET /jobs`        | List all jobs                          |
| `DELETE /job/{id}` | Stop a running job                     |

```bash
just listen                    # Start server on port 7600
just send "Open Safari..."     # Submit a job via Direct
just jobs                      # List all jobs
just job <id>                  # Check a specific job
just latest                    # Full details of the most recent job
just latest 3                  # Full details of the last 3 jobs
```

---

### Direct — CLI Client

> CLI client for the Listen server.

**Python** · v0.1.0 · httpx + Click

Direct is the command-line interface for sending prompts to Listen. It starts jobs, checks their status, and stops them.

| Command  | Purpose                                |
| -------- | -------------------------------------- |
| `start`  | Submit a new job prompt                |
| `get`    | Get current state of a job             |
| `list`   | List all jobs                          |
| `latest` | Show full details of the latest N jobs |
| `stop`   | Stop a running job                     |

---

## Key Patterns

### Cross-App Pipelines

Combine Steer and Drive to build pipelines that span multiple applications without human input:

<p align="center">
  <img src="assets/diagrams/cross-app-pipeline.svg" alt="Cross-App Pipeline" width="700"/>
</p>

```
Read GitHub issue (Browser via OCR) → Run Claude Code (Terminal via Drive) → Log result (Notion via Steer)
```

### Agent-on-Agent Orchestration

One AI agent can control other AI agents through tmux — sending prompts, monitoring output, and managing sessions:

<p align="center">
  <img src="assets/diagrams/agent-inception.svg" alt="Agent Inception" width="500"/>
</p>

A primary Claude Code instance spins up tmux sessions, launches secondary agents, prompts them, monitors their work, and closes them when done. Agent inception — visible in real time.

### Multi-Window Orchestration

Agents can operate across your entire desktop simultaneously — researching in the browser, coding in the terminal, documenting in Notion, monitoring logs:

<p align="center">
  <img src="assets/diagrams/multi-window-tile.svg" alt="Multi-Window Orchestration" width="600"/>
</p>

### Self-Healing Automation

Production-grade agents need resilience. Steer's `wait`, `find`, and `ocr` commands enable self-healing flows that recover from timeouts and errors:

<p align="center">
  <img src="assets/diagrams/self-healing-flow.svg" alt="Self-Healing Flow" width="700"/>
</p>

---

## Custom Agent Support

Steer and Drive are agent-agnostic tools. Any Skill + CLI-based AI agent can use them:

- **Claude Code** — Anthropic's CLI agent
- **Pi Agent** — Custom agent framework
- **Gemini CLI** — Google's CLI agent
- **Codex CLI** — OpenAI's CLI agent
- **OpenCode** — Open-source alternative
- **Cursor CLI** - Cursor's CLI agent

The agent just needs to be able to invoke shell commands. Steer and Drive handle the rest.

---

## Quick Start

```bash
# GUI automation
steer see --app Safari                    # Screenshot Safari
steer ocr --app "VS Code" --store         # OCR all text in VS Code
steer click --text "Submit"               # Click the "Submit" button
steer type "Hello, world"                 # Type text

# Terminal automation
drive session create --name agent-1       # Create tmux session
drive run --session agent-1 "npm test"    # Run command and wait
drive logs --session agent-1              # Capture output
drive fanout --sessions a1,a2,a3 "build"  # Parallel execution
```

---

## Project Structure

```
mac-mini-agent/
├── apps/
│   ├── steer/          # Swift CLI — macOS GUI automation
│   │   └── Sources/
│   │       └── steer/  # 14 command implementations
│   ├── drive/          # Python CLI — tmux terminal control
│   │   └── commands/   # 6 command implementations
│   ├── listen/         # Python — FastAPI job server
│   │   ├── jobs/       # YAML job state files
│   │   └── worker.py   # Agent spawner
│   └── direct/         # Python — CLI client for Listen
└── assets/
    ├── architecture-v3.svg
    ├── architecture-v3-animated.svg
    └── diagrams/       # Animated concept diagrams
```

---

## Setup

The system runs across two machines: a **Mac Mini** that agents control autonomously, and your **primary Mac** where you work and send jobs. Each has a dedicated install command that handles dependencies, configuration, and verification.

### Mac Mini Device (Agent Sandbox)

The Mac Mini is the agent's workstation — it runs Listen, executes jobs, and gives agents full GUI + terminal access.

**Automated setup**: Run the installer directly on the Mac Mini:

```bash
/install-agent-sandbox
```

This installs all dependencies (Swift, tmux, uv, just, yq, Claude Code), builds steer, sets up Python environments, and runs a 10-check verification suite covering screenshots, OCR, tmux sessions, the listen server, and more.

**Manual prerequisites** (must be done through System Settings — the installer will remind you):

| Permission             | Why                                              | How                                                                    |
| ---------------------- | ------------------------------------------------ | ---------------------------------------------------------------------- |
| **Accessibility**      | Steer needs to click, type, and read UI elements | System Settings > Privacy & Security > Accessibility > add Terminal    |
| **Screen Recording**   | Steer needs to capture screenshots (`steer see`) | System Settings > Privacy & Security > Screen Recording > add Terminal |
| **Full Disk Access**   | Required for `systemsetup` and broad file access | System Settings > Privacy & Security > Full Disk Access > add Terminal |
| **Remote Login (SSH)** | Lets you manage the sandbox remotely             | System Settings > General > Sharing > toggle Remote Login on           |

Once installed, start the agent server:

```bash
just listen    # Starts Listen on port 7600
```

---

### Primary Device (Engineer Devbox)

Your laptop is where you send prompts and monitor jobs. It only needs the CLI client tools.

**Automated setup**: Run the installer on your primary Mac:

```bash
/install-engineer-devbox <mac-mini-ip-or-hostname>
```

This installs minimal dependencies (uv, just), configures the sandbox URL, and runs a 6-check verification suite covering network connectivity, the listen server, SSH access, and an end-to-end job test.

Once installed, send jobs:

```bash
just send "Open Safari, navigate to news.ycombinator.com, and read the top 3 headlines"
just jobs              # List all jobs
just job <id>          # Check a specific job
just stop <id>         # Kill a running job
```

**SSH access** (optional, for debugging):

```bash
ssh <user>@<mac-mini-ip>
# or via Bonjour
ssh <user>@<hostname>.local
```

---

## Master Agentic Coding
> Prepare for the future of software engineering

Software engineering has changed... **Have you**? Catch up and move beyond the AI tech industry with [Tactical Agentic Coding](https://agenticengineer.com/tactical-agentic-coding?y=mmag)

Follow the [IndyDevDan YouTube channel](https://www.youtube.com/@indydevdan) to improve your agentic coding advantage.
