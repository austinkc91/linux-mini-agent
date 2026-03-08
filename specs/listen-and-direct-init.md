# Listen & Direct — Remote Agent Job System

Two new apps enabling remote agent execution across machines over HTTP.

```
[Remote Machine]                    [Mac Mini / Worker]

  direct start <url> <prompt>       listen (HTTP server)
       │                                 │
       ├── POST /job ──────────────────▶ │
       │                                 ├── generate job_id
       │                                 ├── write jobs/<id>.yaml (status: running)
       │                                 ├── spawn worker process (non-blocking)
       │                                 │       └── just agent "<prompt>"
       │ ◀── {"job_id": "abc123"} ──────┤
       │                                 │
       │   (server free for new jobs)    │   (worker runs autonomously)
       │                                 │
       ├── GET /job/abc123 ────────────▶ │
       │ ◀── yaml contents ─────────────┤
       │                                 │
       │                                 │   worker finishes → updates yaml
       │                                 │   (status: completed, result: ...)
       ├── GET /job/abc123 ────────────▶ │
       │ ◀── yaml (completed) ──────────┤
```

---

## Apps

### `apps/listen` — HTTP Server + Job Manager

Lightweight HTTP server that accepts job requests, spawns worker processes, and serves job status from YAML files on disk.

**Stack:** Python 3.11+, astral uv, FastAPI, uvicorn, PyYAML

**Core behavior:**
1. Receives `POST /job` with a prompt
2. Generates a job ID (short UUID)
3. Creates `jobs/<id>.yaml` with initial state
4. Spawns a **separate process** that runs `just agent "<prompt>"` from the listen app root
5. Returns the job ID immediately (non-blocking)
6. Worker process updates the YAML file when the agent finishes (status, result, exit_code, duration)
7. The spawned agent receives an `--append-system-prompt` instructing it to write periodic updates and a final summary back to the job YAML file

**The justfile** lives at `apps/listen/justfile`. The `agent` recipe launches a Claude Code agent (or configurable agent) with the given prompt. This gives the spawned agent access to steer and drive from the working directory.

### `apps/direct` — CLI Client

Simple CLI that talks to a listen server over HTTP.

**Stack:** Python 3.11+, astral uv, Click, httpx

---

## PHASE 1: PROJECT STRUCTURE

### Listen

```
apps/listen/
├── pyproject.toml       # uv-managed dependencies
├── main.py              # FastAPI app + server entry point
├── justfile             # Agent launch recipes
├── jobs/                # YAML job files (gitignored)
│   ├── abc123.yaml
│   └── def456.yaml
├── worker.py            # Subprocess worker — runs agent, updates yaml
└── .gitignore           # jobs/
```

### Direct

```
apps/direct/
├── pyproject.toml       # uv-managed dependencies
├── main.py              # Click CLI entry point
└── client.py            # HTTP client wrapper
```

---

## PHASE 2: LISTEN — HTTP API

### Endpoints

#### `POST /job`

Kick off a new agent job.

**Request:**
```json
{
  "prompt": "Open Safari and take a screenshot of the homepage"
}
```

**Response:**
```json
{
  "job_id": "abc123",
  "status": "running"
}
```

**Server behavior:**
1. Generate job ID — first 8 chars of `uuid4().hex`
2. Write initial YAML:
   ```yaml
   id: abc123
   status: running
   prompt: "Open Safari and take a screenshot of the homepage"
   created_at: "2026-03-03T10:30:00Z"
   pid: 12345
   updates: []
   summary: ""
   ```
3. Spawn worker as a subprocess (`subprocess.Popen`) — fire and forget
4. Return job ID

#### `GET /job/{job_id}`

Read current job state.

**Response:** The raw YAML file contents for the job.

```yaml
id: abc123
status: completed
prompt: "Open Safari and take a screenshot of the homepage"
created_at: "2026-03-03T10:30:00Z"
completed_at: "2026-03-03T10:32:15Z"
duration_seconds: 135
pid: 12345
exit_code: 0
updates:
- "Launched Safari and navigated to homepage"
- "Captured screenshot and accessibility snapshot"
summary: |
  Opened Safari, captured the homepage accessibility tree (42 elements),
  and saved a screenshot to /tmp/steer/a1b2c3d4.png.
```

**Status values:** `running`, `completed`, `failed`, `stopped`

#### `GET /jobs`

List all jobs.

**Response:**
```yaml
jobs:
- id: abc123
  status: completed
  prompt: "Open Safari and take a screenshot..."
  created_at: "2026-03-03T10:30:00Z"
- id: def456
  status: running
  prompt: "Run npm test in project X..."
  created_at: "2026-03-03T10:35:00Z"
```

#### `DELETE /job/{job_id}`

Stop a running job. Sends SIGTERM to the worker process PID stored in the YAML.

**Response:**
```json
{
  "job_id": "def456",
  "status": "stopped"
}
```

**Behavior:**
1. Read PID from job YAML
2. Send SIGTERM to the process
3. Update YAML status to `stopped`

---

## PHASE 3: LISTEN — WORKER PROCESS

`worker.py` — Runs as a standalone subprocess spawned by the server.

**Invocation:** `uv run worker.py <job_id> <prompt>`

**Behavior:**

```
1. Read jobs/<job_id>.yaml (confirm it exists)
2. Run: just agent "<prompt>" "<job_id>"
   - Working directory: apps/listen/ (so justfile is found)
   - Justfile `cd`s to repo root before launching agent (agent cwd = steer/)
   - Captures stdout/stderr
3. On completion:
   - Update YAML: status → completed/failed
   - Write: exit_code, duration_seconds, completed_at
   - (summary and updates are written by the agent itself during execution)
4. Exit
```

The worker owns status/timing fields. The agent owns `updates` and `summary` fields — it appends updates and writes a summary as part of its system prompt instructions.

---

## PHASE 4: LISTEN — JUSTFILE & SYSTEM PROMPT

```justfile
# apps/listen/justfile

# Launch an agent with the given prompt
# job_id is passed so the agent knows which YAML file to update
root := "../.."
sys_prompt := `cat ../../.claude/agents/listen-drive-and-steer-system-prompt.md`

# Launch Claude Code agent from repo root
agent-claude prompt job_id:
    cd {{root}} && claude --dangerously-skip-permissions \
      -p "{{prompt}}" \
      --append-system-prompt "{{replace(sys_prompt, '{{JOB_ID}}', job_id)}}"

# Launch Pi agent from repo root
agent-pi prompt job_id:
    cd {{root}} && pi -p "{{prompt}}" \
      --append-system-prompt "{{replace(sys_prompt, '{{JOB_ID}}', job_id)}}"

# Default agent (claude)
agent prompt job_id: (agent-claude prompt job_id)
```

The justfile is the single point of configuration for how agents are launched. Adding a new agent type = one new recipe. Both `claude` and `pi` support `--append-system-prompt` and `-p` for non-interactive mode.

### `.claude/agents/listen-drive-and-steer-system-prompt.md`

Appended to the agent's system prompt. Instructs the agent to write progress updates and a final summary to its job YAML file. Lives at the repo root level so it can reference the full steer/drive toolset context.

```markdown
## Job Reporting

You are running as job `{{JOB_ID}}`. Your job file is at `jobs/{{JOB_ID}}.yaml`.

### Progress Updates

Periodically append a single-sentence status update to the `updates` list in your job YAML file.
Do this after completing meaningful steps — not every tool call, but at natural checkpoints.

Example — read the file, append to the updates list, write it back:

```bash
# Use yq to append an update (keeps YAML valid)
yq -i '.updates += ["Set up test environment and installed dependencies"]' jobs/{{JOB_ID}}.yaml
```

### Summary

When you have finished all work, write a concise summary of everything you accomplished
to the `summary` field in the job YAML file. This is the last thing you do before exiting.

```bash
yq -i '.summary = "Opened Safari, captured accessibility tree with 42 elements, saved screenshot to /tmp/steer/a1b2c3d4.png"' jobs/{{JOB_ID}}.yaml
```
```

### Updated project structure

```
.claude/agents/
└── listen-drive-and-steer-system-prompt.md   # Appended system prompt template

apps/listen/
├── pyproject.toml
├── main.py
├── justfile
├── jobs/
├── worker.py
└── .gitignore
```

---

## PHASE 5: DIRECT — CLI

Entry point: `apps/direct/main.py`

### Commands

#### `start`

```bash
python main.py start <url> "<prompt>"
```

- POST to `<url>/job` with the prompt
- Print the returned job ID

#### `get`

```bash
python main.py get <url> <job_id>
```

- GET `<url>/job/<job_id>`
- Print the YAML response

#### `list`

```bash
python main.py list <url>
```

- GET `<url>/jobs`
- Print the YAML response

#### `stop`

```bash
python main.py stop <url> <job_id>
```

- DELETE `<url>/job/<job_id>`
- Print confirmation

---

## PHASE 6: BUILD & VERIFY

### Listen

```bash
cd apps/listen
uv sync
```

**Start server:**
```bash
uv run main.py
# → Uvicorn running on http://0.0.0.0:7600
```

Port `7600` — easy to remember, unlikely to conflict.

### Direct

```bash
cd apps/direct
uv sync
```

### Smoke test (local)

```bash
# Terminal 1: start listen
cd apps/listen && uv run main.py

# Terminal 2: kick off a job
cd apps/direct && uv run main.py start http://localhost:7600 "echo hello from agent"

# Check status
uv run main.py get http://localhost:7600 <job_id>

# List all jobs
uv run main.py list http://localhost:7600

# Stop a job
uv run main.py stop http://localhost:7600 <job_id>
```

**Success criteria:**
- [ ] POST /job returns job_id immediately (< 100ms)
- [ ] Worker spawns as separate process (server doesn't block)
- [ ] YAML file created in jobs/ with running status
- [ ] GET /job/<id> returns current YAML state
- [ ] After agent finishes, YAML shows completed + result
- [ ] GET /jobs lists all jobs
- [ ] DELETE /job/<id> kills the worker process and updates status
- [ ] Server handles multiple concurrent jobs

---

## KNOWN CONSTRAINTS

1. **No auth** — First version is bare. Add API key header later if exposed beyond local network.
2. **No file streaming** — Screenshots stay on the worker machine. If the remote agent needs them, that's a future `/job/<id>/files` endpoint.
3. **Single machine** — Each listen instance serves one machine. Scaling = run listen on each machine, direct points at whichever one.
4. **YAML as database** — Fine for tens/hundreds of jobs. If it ever needs to handle thousands, swap to SQLite. Unlikely.
