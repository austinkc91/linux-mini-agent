---
description: Load foundational context about the linux-mini-agent codebase — architecture, apps, skills, and key patterns
---

# Purpose

Understand the linux-mini-agent monorepo: a Linux desktop automation framework with five apps (steer, drive, listen, direct, telegram) that give AI agents full control of a Linux desktop via GUI and terminal automation, with remote control via Telegram.

## Workflow

1. Read project overview and task runner:
   - READ `README.md`
   - READ `justfile`

2. Read each app's config:
   - READ `apps/steer/pyproject.toml`
   - READ `apps/drive/pyproject.toml`
   - READ `apps/listen/pyproject.toml`
   - READ `apps/direct/pyproject.toml`
   - READ `apps/telegram/pyproject.toml`

3. Read the agent skills and prompts:
   - READ `.claude/skills/steer/SKILL.md`
   - READ `.claude/skills/drive/SKILL.md`
   - READ `.claude/agents/listen-drive-and-steer-system-prompt.md`
   - READ `.claude/commands/listen-drive-and-steer-user-prompt.md`

4. Read entry points and agent launch config:
   - READ `apps/steer/main.py`
   - READ `apps/drive/main.py`
   - READ `apps/listen/main.py`
   - READ `apps/listen/justfile`
   - READ `apps/direct/main.py`
   - READ `apps/telegram/main.py`

5. Summarize: purpose, architecture (5 apps), stack (all Python), key patterns (observe-act-verify, sentinel protocol, job YAML tracking, element IDs, Telegram remote control), and how the pieces connect
