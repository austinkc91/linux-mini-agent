# steer project justfile
set dotenv-load := true

export VIRTUAL_ENV := ""

_sandbox_url := env("AGENT_SANDBOX_URL", "")
default_url := if _sandbox_url == "" { "http://localhost:7600" } else { _sandbox_url }

# List available commands
default:
    @just --list

# Start the listen server
listen:
    cd apps/listen && uv run python main.py

# Send a job to the listen server
send prompt url=default_url:
    cd apps/direct && uv run python main.py start {{url}} "{{prompt}}"

# Send a job from a local file
sendf file url=default_url:
    #!/usr/bin/env bash
    prompt="$(cat '{{file}}')"
    cd apps/direct && uv run python main.py start '{{url}}' "$prompt"

# Get a job's status
job id url=default_url:
    cd apps/direct && uv run python main.py get {{url}} {{id}}

# List all jobs (pass --archived to see archived)
jobs *flags:
    cd apps/direct && uv run python main.py list {{default_url}} {{flags}}

# Show full details of the latest N jobs (default: 1)
latest n="1" url=default_url:
    cd apps/direct && uv run python main.py latest {{url}} {{n}}

# Stop a running job
stop id url=default_url:
    cd apps/direct && uv run python main.py stop {{url}} {{id}}

# Archive all jobs
clear url=default_url:
    cd apps/direct && uv run python main.py clear {{url}}

# Prime Claude Code with codebase context
prime:
    claude --dangerously-skip-permissions "/prime"

# Prime Pi with codebase context (uses ipi if available, otherwise pi)
piprime:
    #!/usr/bin/env bash
    if command -v ipi &>/dev/null; then
        ipi "/prime"
    else
        pi --prompt-template .claude/commands "/prime"
    fi



steer1 := `cat specs/research-macbooks.md`
steer2 := `cat specs/hackernews-apple-research.md`
steer3 := `cat specs/notes-running-apps.md`

# --- Send test prompts (run remotely) ---

send1-cc:
    just send "{{steer1}}"

send2-cc:
    just send "{{steer2}}"

send3-cc:
    just send "{{steer3}}"

# --- Local test prompts (run directly, no listen server) ---

# Run steer1 with Claude Code
steer1-cc:
    claude --dangerously-skip-permissions "/listen-drive-and-steer-user-prompt {{steer1}}"

# Run steer1 with Pi
steer1-pi:
    #!/usr/bin/env bash
    if command -v ipi &>/dev/null; then
        ipi --skill .claude/skills --prompt-template .claude/commands "/listen-drive-and-steer-user-prompt {{steer1}}"
    else
        pi --skill .claude/skills --prompt-template .claude/commands "/listen-drive-and-steer-user-prompt {{steer1}}"
    fi

# Run steer2 with Claude Code
steer2-cc:
    claude --dangerously-skip-permissions "/listen-drive-and-steer-user-prompt {{steer2}}"

# Run steer2 with Pi
steer2-pi:
    #!/usr/bin/env bash
    if command -v ipi &>/dev/null; then
        ipi --skill .claude/skills --prompt-template .claude/commands "/listen-drive-and-steer-user-prompt {{steer2}}"
    else
        pi --skill .claude/skills --prompt-template .claude/commands "/listen-drive-and-steer-user-prompt {{steer2}}"
    fi

# Run steer3 with Claude Code
steer3-cc:
    claude --dangerously-skip-permissions "/listen-drive-and-steer-user-prompt {{steer3}}"

# Run steer3 with Pi
steer3-pi:
    #!/usr/bin/env bash
    if command -v ipi &>/dev/null; then
        ipi --skill .claude/skills --prompt-template .claude/commands "/listen-drive-and-steer-user-prompt {{steer3}}"
    else
        pi --skill .claude/skills --prompt-template .claude/commands "/listen-drive-and-steer-user-prompt {{steer3}}"
    fi

# Run a custom prompt with Claude Code
steer-cc prompt:
    claude --dangerously-skip-permissions "/listen-drive-and-steer-user-prompt {{prompt}}"

# Run a custom prompt with Pi
steer-pi prompt:
    #!/usr/bin/env bash
    if command -v ipi &>/dev/null; then
        ipi --skill .claude/skills --prompt-template .claude/commands "/listen-drive-and-steer-user-prompt {{prompt}}"
    else
        pi --skill .claude/skills --prompt-template .claude/commands "/listen-drive-and-steer-user-prompt {{prompt}}"
    fi

# --- Demo walkthrough ---
# 1. just listen          (start server in one terminal)
# 2. just send "prompt"   (kick off a job from another terminal)
# 3. just jobs            (see all jobs)
# 4. just job <id>        (check a specific job)
# 5. just stop <id>       (kill a running job)
