---
description: Load foundational context about the steer codebase — architecture, apps, skills, and key patterns
---

# Purpose

Understand the steer monorepo: a macOS automation framework with four apps (steer, drive, listen, direct) that give AI agents full control of a Mac via GUI and terminal automation.

## Workflow

1. Read project overview and task runner:
   - READ `README.md`
   - READ `justfile`

2. Read each app's config:
   - READ `apps/steer/Package.swift`
   - READ `apps/drive/pyproject.toml`
   - READ `apps/listen/pyproject.toml`
   - READ `apps/direct/pyproject.toml`

3. Read the agent skills and prompts:
   - READ `.claude/skills/steer/SKILL.md`
   - READ `.claude/skills/drive/SKILL.md`
   - READ `.claude/agents/listen-drive-and-steer-system-prompt.md`
   - READ `.claude/commands/listen-drive-and-steer-user-prompt.md`

4. Read entry points and agent launch config:
   - READ `apps/steer/Sources/steer/Steer.swift`
   - READ `apps/drive/main.py`
   - READ `apps/listen/main.py`
   - READ `apps/listen/justfile`
   - READ `apps/direct/main.py`

5. Summarize: purpose, architecture (4 apps), stack (Swift + Python), key patterns (observe-act-verify, sentinel protocol, job YAML tracking, element IDs), and how the pieces connect
