import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import yaml
from fastapi import FastAPI, HTTPException, UploadFile, File, Request, Response, Cookie
from fastapi.responses import HTMLResponse, PlainTextResponse, FileResponse, RedirectResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import Optional

import auth

UPLOAD_DIR = Path("/tmp/dashboard-uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50MB

import cron_manager

JOBS_DIR = Path(__file__).parent / "jobs"
JOBS_DIR.mkdir(exist_ok=True)
ARCHIVED_DIR = JOBS_DIR / "archived"
MAX_WORKERS = 4
MAX_PROMPT_LENGTH = 100_000  # 100KB max prompt size
_worker_semaphore = threading.Semaphore(MAX_WORKERS)


def _atomic_yaml_write(path: Path, data: dict):
    """Write YAML atomically: write to temp file then rename."""
    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=path.parent, suffix=".tmp", prefix=path.stem
    )
    try:
        with os.fdopen(tmp_fd, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _recover_orphaned_jobs():
    """Mark any 'running' jobs whose worker PID is dead as failed.

    This handles cases where the worker was killed (OOM, SIGKILL, reboot)
    before it could update the job YAML.
    """
    for f in JOBS_DIR.glob("*.yaml"):
        try:
            with open(f) as fh:
                data = yaml.safe_load(fh)
            if data.get("status") != "running":
                continue
            pid = data.get("pid", 0)
            if pid:
                try:
                    os.kill(pid, 0)  # Check if process is alive (signal 0)
                    continue  # Still running, leave it alone
                except ProcessLookupError:
                    pass  # Process is dead — mark as failed
            data["status"] = "failed"
            data["exit_code"] = -1
            data["completed_at"] = datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
            if not data.get("summary"):
                data["summary"] = (
                    "Job was interrupted unexpectedly (worker process died). "
                    "This may have been caused by OOM killer, system reboot, or an external signal."
                )
            _atomic_yaml_write(f, data)
            print(f"Recovered orphaned job: {data.get('id')}")
        except Exception as e:
            print(f"Error recovering job {f.name}: {e}")


def _auto_archive_old_jobs(max_age_days: int = 7):
    """Archive completed/failed/stopped jobs older than max_age_days."""
    ARCHIVED_DIR.mkdir(exist_ok=True)
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    count = 0
    for f in JOBS_DIR.glob("*.yaml"):
        try:
            with open(f) as fh:
                data = yaml.safe_load(fh)
            if data.get("status") in ("completed", "failed", "stopped"):
                completed = data.get("completed_at") or data.get("created_at", "")
                if completed:
                    job_time = datetime.fromisoformat(completed.replace("Z", "+00:00"))
                    if job_time < cutoff:
                        shutil.move(str(f), str(ARCHIVED_DIR / f.name))
                        log = f.with_suffix(".log")
                        if log.exists():
                            shutil.move(str(log), str(ARCHIVED_DIR / log.name))
                        count += 1
        except Exception:
            pass
    if count:
        print(f"Auto-archived {count} old job(s)")


def _cleanup_steer_snapshots():
    """Clean up old screenshot snapshots from /tmp/steer."""
    steer_dir = Path(tempfile.gettempdir()) / "steer"
    if not steer_dir.is_dir():
        return
    import time
    cutoff = time.time() - 4 * 3600  # 4 hours
    removed = 0
    pngs = sorted(steer_dir.glob("*.png"), key=lambda p: p.stat().st_mtime)
    for p in pngs:
        try:
            if p.stat().st_mtime < cutoff:
                p.unlink()
                removed += 1
        except OSError:
            pass
    # Also cap at 50 files
    remaining = sorted(steer_dir.glob("*.png"), key=lambda p: p.stat().st_mtime)
    while len(remaining) > 50:
        try:
            remaining.pop(0).unlink()
            removed += 1
        except OSError:
            pass
    if removed:
        print(f"Cleaned up {removed} stale screenshot(s) from /tmp/steer")


def _periodic_maintenance():
    """Run archival and cleanup periodically in a background thread."""
    import time as _time
    while True:
        _time.sleep(3600)  # Every hour
        try:
            _auto_archive_old_jobs()
        except Exception as e:
            print(f"Periodic archive error: {e}")
        try:
            _cleanup_steer_snapshots()
        except Exception as e:
            print(f"Periodic snapshot cleanup error: {e}")


@asynccontextmanager
async def lifespan(app):
    _recover_orphaned_jobs()
    _auto_archive_old_jobs()
    _cleanup_steer_snapshots()
    cron_manager.start()
    maintenance_thread = threading.Thread(target=_periodic_maintenance, daemon=True)
    maintenance_thread.start()
    yield
    cron_manager.stop()


app = FastAPI(lifespan=lifespan)


# --- Authentication ---

# Routes that don't require login
_PUBLIC_PATHS = {"/auth/login", "/login", "/health"}
# Routes accessible from localhost without auth (internal API)
_LOCALHOST_PATHS = {"/job", "/jobs", "/cron", "/crons", "/reset", "/upload"}


def _is_localhost(request: Request) -> bool:
    """Check if request comes from localhost."""
    client = request.client
    if not client:
        return False
    return client.host in ("127.0.0.1", "::1", "localhost")


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path

    # Public routes always allowed
    if path in _PUBLIC_PATHS or path.startswith("/auth/"):
        return await call_next(request)

    # Static uploads always allowed (they have unique filenames)
    if path.startswith("/uploads/"):
        return await call_next(request)

    # Localhost requests to API endpoints skip auth (internal services)
    if _is_localhost(request) and any(path.startswith(p) for p in _LOCALHOST_PATHS):
        return await call_next(request)

    # Check session cookie
    token = request.cookies.get(auth.SESSION_COOKIE)
    if token and auth.get_session_user(token):
        return await call_next(request)

    # Not authenticated — redirect browser requests to login, return 401 for API
    if path.startswith("/api/"):
        return JSONResponse(status_code=401, content={"detail": "Not authenticated"})
    return RedirectResponse(url="/login", status_code=302)


class LoginRequest(BaseModel):
    username: str
    password: str


@app.get("/login", response_class=HTMLResponse)
def login_page():
    login_file = Path(__file__).parent / "login.html"
    return login_file.read_text()


@app.post("/auth/login")
def login(req: LoginRequest, response: Response):
    if not auth.verify_password(req.username, req.password):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = auth.create_session(req.username)
    response = JSONResponse(content={"ok": True})
    response.set_cookie(
        key=auth.SESSION_COOKIE,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 30,  # 30 days
    )
    return response


@app.post("/auth/logout")
def logout(request: Request):
    token = request.cookies.get(auth.SESSION_COOKIE)
    if token:
        auth.destroy_session(token)
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie(auth.SESSION_COOKIE)
    return response


# --- End Authentication ---


class JobRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=MAX_PROMPT_LENGTH)
    chain: list[str] = Field(default_factory=list)  # Follow-up prompts to run after this job
    chain_from: Optional[str] = None  # Parent job ID (set automatically for chained jobs)
    files: list[str] = Field(default_factory=list)  # Uploaded filenames from /upload endpoint
    submitted_by: Optional[str] = None  # Username of the person who submitted this job


def _submit_next_in_chain(job_id: str):
    """Check if a completed job has remaining chain steps and submit the next one."""
    job_file = JOBS_DIR / f"{job_id}.yaml"
    if not job_file.exists():
        return

    with open(job_file) as f:
        data = yaml.safe_load(f)

    if data.get("status") != "completed":
        return

    chain = data.get("chain", [])
    if not chain:
        return

    next_prompt = chain[0]
    remaining = chain[1:]

    # Inject previous job's summary as context
    prev_summary = data.get("summary", "")
    if prev_summary:
        contextualized_prompt = (
            f"This is a chained job. The previous job (ID: {job_id}) completed with this result:\n"
            f"---\n{prev_summary}\n---\n\n"
            f"Now do the following:\n{next_prompt}"
        )
    else:
        contextualized_prompt = next_prompt

    # Submit via internal function (not HTTP) to avoid concurrency issues
    try:
        import httpx
        resp = httpx.post(
            "http://localhost:7600/job",
            json={
                "prompt": contextualized_prompt,
                "chain": remaining,
                "chain_from": job_id,
            },
            timeout=10,
        )
        if resp.status_code == 200:
            next_id = resp.json().get("job_id", "?")
            print(f"Chain: job {job_id} → job {next_id} ({len(remaining)} remaining)")
        else:
            print(f"Chain: failed to submit next job after {job_id}: {resp.status_code}")
    except Exception as e:
        print(f"Chain: error submitting next job after {job_id}: {e}")


@app.post("/job")
def create_job(req: JobRequest):
    # Check concurrency limit
    if not _worker_semaphore.acquire(blocking=False):
        raise HTTPException(
            status_code=429,
            detail=f"Too many concurrent jobs (max {MAX_WORKERS}). Try again later.",
        )

    job_id = uuid4().hex[:8]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Build prompt with file attachment context
    prompt = req.prompt
    if req.files:
        file_paths = []
        for fname in req.files:
            fpath = UPLOAD_DIR / fname
            if fpath.exists():
                file_paths.append(str(fpath))
        if file_paths:
            prompt += "\n\nAttached files:\n" + "\n".join(f"- {p}" for p in file_paths)

    # Look up user info if submitted_by is provided
    submitted_by = req.submitted_by
    user_email = None
    if submitted_by:
        user_info = auth.lookup_user(submitted_by)
        if user_info:
            user_email = user_info.get("email")
            submitted_by = user_info.get("display_name", submitted_by)

    job_data = {
        "id": job_id,
        "status": "running",
        "prompt": prompt,
        "submitted_by": submitted_by,
        "submitted_by_email": user_email,
        "created_at": now,
        "pid": 0,
        "updates": [],
        "summary": "",
        "attachments": [],
    }

    # Add chain fields if present
    if req.chain:
        job_data["chain"] = req.chain
    if req.chain_from:
        job_data["chain_from"] = req.chain_from

    # Write YAML before spawning worker (worker reads it on startup)
    job_file = JOBS_DIR / f"{job_id}.yaml"
    _atomic_yaml_write(job_file, job_data)

    # Spawn the worker process (in its own process group for clean shutdown)
    worker_path = Path(__file__).parent / "worker.py"
    log_file = JOBS_DIR / f"{job_id}.log"
    log_fh = open(log_file, "w")

    def _run_worker():
        try:
            proc = subprocess.Popen(
                [sys.executable, str(worker_path), job_id, prompt],
                cwd=str(Path(__file__).parent),
                stdout=log_fh,
                stderr=log_fh,
                start_new_session=True,
            )

            # Update PID after spawn
            job_data["pid"] = proc.pid
            _atomic_yaml_write(job_file, job_data)

            proc.wait()
        finally:
            _worker_semaphore.release()
            log_fh.close()
            # After worker completes, check for chain continuation
            threading.Thread(
                target=_submit_next_in_chain, args=(job_id,), daemon=True
            ).start()

    # Start worker in background thread to manage semaphore lifecycle
    worker_thread = threading.Thread(target=_run_worker, daemon=True)
    worker_thread.start()

    return {"job_id": job_id, "status": "running"}


@app.get("/job/{job_id}", response_class=PlainTextResponse)
def get_job(job_id: str):
    job_file = JOBS_DIR / f"{job_id}.yaml"
    if not job_file.exists():
        raise HTTPException(status_code=404, detail="Job not found")
    return job_file.read_text()


@app.get("/jobs", response_class=PlainTextResponse)
def list_jobs(archived: bool = False):
    search_dir = ARCHIVED_DIR if archived else JOBS_DIR
    jobs = []
    for f in sorted(search_dir.glob("*.yaml")):
        with open(f) as fh:
            data = yaml.safe_load(fh)
        jobs.append({
            "id": data.get("id"),
            "status": data.get("status"),
            "prompt": data.get("prompt"),
            "created_at": data.get("created_at"),
        })
    result = yaml.dump({"jobs": jobs}, default_flow_style=False, sort_keys=False)
    return result


@app.post("/jobs/clear")
def clear_jobs():
    ARCHIVED_DIR.mkdir(exist_ok=True)
    count = 0
    for f in JOBS_DIR.glob("*.yaml"):
        shutil.move(str(f), str(ARCHIVED_DIR / f.name))
        count += 1
    return {"archived": count}


@app.delete("/job/{job_id}")
def stop_job(job_id: str):
    job_file = JOBS_DIR / f"{job_id}.yaml"
    if not job_file.exists():
        raise HTTPException(status_code=404, detail="Job not found")

    with open(job_file) as f:
        data = yaml.safe_load(f)

    pid = data.get("pid")
    if pid:
        # Send SIGTERM to process group to kill worker + children
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError, OSError):
            # Fallback to single process kill
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass

    # Also kill the tmux session directly
    session_name = data.get("session", f"job-{job_id}")
    subprocess.run(
        ["tmux", "kill-session", "-t", session_name],
        capture_output=True, check=False,
    )

    data["status"] = "stopped"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    data["completed_at"] = now
    _atomic_yaml_write(job_file, data)

    return {"job_id": job_id, "status": "stopped"}


class CronRequest(BaseModel):
    name: str
    schedule: str  # crontab expression, e.g. "3 7 * * *"
    prompt: str
    timezone: str = "US/Central"
    enabled: bool = True


class CronUpdate(BaseModel):
    name: Optional[str] = None
    schedule: Optional[str] = None
    prompt: Optional[str] = None
    timezone: Optional[str] = None
    enabled: Optional[bool] = None


@app.post("/cron")
def create_cron(req: CronRequest):
    try:
        cron = cron_manager.add_cron(
            name=req.name,
            schedule=req.schedule,
            prompt=req.prompt,
            timezone=req.timezone,
            enabled=req.enabled,
        )
        return cron
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/crons")
def list_crons():
    return {"crons": cron_manager.list_crons()}


@app.get("/cron/{cron_id}")
def get_cron(cron_id: str):
    cron = cron_manager.get_cron(cron_id)
    if not cron:
        raise HTTPException(status_code=404, detail="Cron not found")
    return cron


@app.put("/cron/{cron_id}")
def update_cron(cron_id: str, req: CronUpdate):
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    cron = cron_manager.update_cron(cron_id, **updates)
    if not cron:
        raise HTTPException(status_code=404, detail="Cron not found")
    return cron


@app.delete("/cron/{cron_id}")
def delete_cron(cron_id: str):
    if not cron_manager.delete_cron(cron_id):
        raise HTTPException(status_code=404, detail="Cron not found")
    return {"deleted": cron_id}


@app.post("/cron/{cron_id}/trigger")
def trigger_cron(cron_id: str):
    if not cron_manager.trigger_cron(cron_id):
        raise HTTPException(status_code=404, detail="Cron not found")
    return {"triggered": cron_id}


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload a file for attachment to a job."""
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 50MB)")

    # Generate unique filename preserving extension
    ext = Path(file.filename or "file").suffix or ""
    unique_name = f"{uuid4().hex[:12]}{ext}"
    dest = UPLOAD_DIR / unique_name
    dest.write_bytes(content)

    return {"filename": unique_name, "original_name": file.filename, "size": len(content), "path": str(dest)}


@app.get("/uploads/{filename}")
def serve_upload(filename: str):
    """Serve an uploaded file (for previews)."""
    filepath = UPLOAD_DIR / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(filepath)


@app.get("/api/job/{job_id}")
def api_get_job(job_id: str):
    """JSON endpoint for a single job (used by dashboard chat polling)."""
    job_file = JOBS_DIR / f"{job_id}.yaml"
    if not job_file.exists():
        raise HTTPException(status_code=404, detail="Job not found")
    with open(job_file) as f:
        data = yaml.safe_load(f)
    attachments = data.get("attachments", [])
    attachment_info = []
    for i, path in enumerate(attachments):
        p = Path(path)
        attachment_info.append({
            "index": i,
            "filename": p.name,
            "path": str(p),
            "exists": p.exists(),
            "is_image": p.suffix.lower() in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"},
            "url": f"/api/job/{job_id}/attachment/{i}",
        })
    return {
        "id": data.get("id"),
        "status": data.get("status"),
        "summary": data.get("summary", ""),
        "updates": data.get("updates", []),
        "attachments": attachment_info,
        "created_at": data.get("created_at"),
        "completed_at": data.get("completed_at"),
    }


@app.get("/api/job/{job_id}/attachment/{index}")
def serve_job_attachment(job_id: str, index: int):
    """Serve a file from a job's attachments list."""
    job_file = JOBS_DIR / f"{job_id}.yaml"
    if not job_file.exists():
        raise HTTPException(status_code=404, detail="Job not found")
    with open(job_file) as f:
        data = yaml.safe_load(f)
    attachments = data.get("attachments", [])
    if index < 0 or index >= len(attachments):
        raise HTTPException(status_code=404, detail="Attachment not found")
    filepath = Path(attachments[index])
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")
    return FileResponse(filepath, filename=filepath.name)


@app.get("/api/me")
def api_me(request: Request):
    """Return the currently logged-in username."""
    token = request.cookies.get(auth.SESSION_COOKIE)
    username = auth.get_session_user(token) if token else None
    return {"username": username}


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    """Serve the web dashboard."""
    dashboard_file = Path(__file__).parent / "dashboard.html"
    if not dashboard_file.exists():
        raise HTTPException(status_code=404, detail="Dashboard not found")
    return dashboard_file.read_text()


@app.get("/api/status")
def api_status():
    """API endpoint for dashboard: jobs + crons + system info."""
    # Active jobs
    active_jobs = []
    for f in sorted(JOBS_DIR.glob("*.yaml"), reverse=True):
        try:
            with open(f) as fh:
                data = yaml.safe_load(fh)
            # Extract the actual user request from context-wrapped prompts
            raw_prompt = data.get("prompt", "")
            display_prompt = raw_prompt
            if "Current request:" in raw_prompt:
                display_prompt = raw_prompt.split("Current request:", 1)[1].strip()
            job_id = data.get("id")
            attachments = data.get("attachments", [])
            attachment_info = []
            for idx, apath in enumerate(attachments):
                p = Path(apath)
                attachment_info.append({
                    "index": idx,
                    "filename": p.name,
                    "is_image": p.suffix.lower() in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"},
                    "url": f"/api/job/{job_id}/attachment/{idx}",
                })
            active_jobs.append({
                "id": job_id,
                "status": data.get("status"),
                "prompt": (display_prompt[:200] + "...") if len(display_prompt) > 200 else display_prompt,
                "created_at": data.get("created_at"),
                "completed_at": data.get("completed_at"),
                "duration_seconds": data.get("duration_seconds"),
                "summary": (data.get("summary", "")[:300] + "...") if len(data.get("summary", "")) > 300 else data.get("summary", ""),
                "updates": data.get("updates", []),
                "chain_from": data.get("chain_from"),
                "chain": data.get("chain", []),
                "attachments": attachment_info,
            })
        except Exception:
            pass

    # Crons
    crons = cron_manager.list_crons()

    # System info
    import psutil
    cpu = psutil.cpu_percent(interval=0.1)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    return {
        "jobs": active_jobs,
        "crons": crons,
        "system": {
            "cpu_percent": cpu,
            "memory_used_gb": round(mem.used / (1024**3), 1),
            "memory_total_gb": round(mem.total / (1024**3), 1),
            "memory_percent": mem.percent,
            "disk_used_gb": round(disk.used / (1024**3), 1),
            "disk_total_gb": round(disk.total / (1024**3), 1),
            "disk_percent": round(disk.percent, 1),
            "max_workers": MAX_WORKERS,
        },
    }


@app.post("/reset/soft")
def soft_reset():
    """Stop all running jobs, kill stale claude processes, kill orphan tmux sessions, restart listen."""
    results = {}

    # 1. Stop all running jobs
    stopped = 0
    for f in JOBS_DIR.glob("*.yaml"):
        try:
            with open(f) as fh:
                data = yaml.safe_load(fh)
            if data.get("status") == "running":
                try:
                    stop_job(data["id"])
                    stopped += 1
                except Exception:
                    pass
        except Exception:
            pass
    results["jobs_stopped"] = stopped

    # 2. Kill stale claude processes (not belonging to active job sessions)
    try:
        r = subprocess.run(
            ["bash", "-c", """
            active=$(tmux list-sessions -F '#{session_name}' 2>/dev/null | grep '^job-' || true)
            killed=0
            for pid in $(pgrep -f 'claude' 2>/dev/null || true); do
                cmdline=$(cat /proc/$pid/cmdline 2>/dev/null | tr '\\0' ' ' || true)
                is_active=false
                for session in $active; do
                    if echo "$cmdline" | grep -q "$session"; then
                        is_active=true
                        break
                    fi
                done
                if [ "$is_active" = "false" ]; then
                    kill $pid 2>/dev/null && killed=$((killed+1))
                fi
            done
            echo "$killed"
            """],
            capture_output=True, text=True, timeout=15,
        )
        results["processes_killed"] = int(r.stdout.strip() or "0")
    except Exception as e:
        results["processes_killed"] = f"error: {e}"

    # 3. Kill orphan tmux job sessions
    try:
        r = subprocess.run(
            ["bash", "-c", f"""
            killed=0
            for session in $(tmux list-sessions -F '#{{session_name}}' 2>/dev/null | grep '^job-' || true); do
                job_id=${{session#job-}}
                job_file="{JOBS_DIR}/$job_id.yaml"
                if [ -f "$job_file" ]; then
                    status=$(grep '^status:' "$job_file" | awk '{{print $2}}')
                    if [ "$status" != "running" ]; then
                        tmux kill-session -t "$session" 2>/dev/null && killed=$((killed+1))
                    fi
                else
                    tmux kill-session -t "$session" 2>/dev/null && killed=$((killed+1))
                fi
            done
            echo "$killed"
            """],
            capture_output=True, text=True, timeout=15,
        )
        results["sessions_killed"] = int(r.stdout.strip() or "0")
    except Exception as e:
        results["sessions_killed"] = f"error: {e}"

    # 4. Schedule listen service restart (after response is sent)
    def _restart_listen():
        import time
        time.sleep(1)
        subprocess.run(["sudo", "systemctl", "restart", "linux-agent-listen"],
                       capture_output=True, timeout=15)
    import threading
    threading.Thread(target=_restart_listen, daemon=True).start()
    results["service_restart"] = "scheduled"

    return results


@app.post("/reset/hard")
def hard_reset():
    """Full system reboot."""
    def _reboot():
        import time
        time.sleep(1)
        subprocess.Popen(["sudo", "reboot"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    import threading
    threading.Thread(target=_reboot, daemon=True).start()
    return {"status": "rebooting"}


if __name__ == "__main__":
    import socket
    import uvicorn

    # Enable SO_REUSEADDR so restarts don't fail with "address already in use"
    config = uvicorn.Config(app, host="0.0.0.0", port=7600)
    config.socket_options = [(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)]
    server = uvicorn.Server(config)
    server.run()
