"""Listen server — FastAPI job manager with SQLite storage.

Accepts job prompts, spawns Claude Code workers in tmux sessions,
tracks progress, and serves results via HTTP API.
"""

import asyncio
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import yaml
from fastapi import FastAPI, HTTPException, UploadFile, File, Request, Response
from fastapi.responses import (
    HTMLResponse,
    PlainTextResponse,
    FileResponse,
    RedirectResponse,
    JSONResponse,
)
from pydantic import BaseModel, Field
from typing import Optional

import auth
import db
import cron_manager

UPLOAD_DIR = Path("/tmp/dashboard-uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50MB

JOBS_DIR = db.JOBS_DIR  # For log files
JOBS_DIR.mkdir(exist_ok=True)

MAX_WORKERS = 4
MAX_PROMPT_LENGTH = 100_000  # 100KB max prompt size
_worker_semaphore: asyncio.Semaphore = asyncio.Semaphore(MAX_WORKERS)
_active_workers: dict[str, asyncio.subprocess.Process] = {}

# ---------------------------------------------------------------------------
# Systemd watchdog / sd_notify
# ---------------------------------------------------------------------------

_notify_socket: Optional[socket.socket] = None


def _sd_notify(msg: str):
    """Send a message to systemd via the NOTIFY_SOCKET."""
    global _notify_socket
    addr = os.environ.get("NOTIFY_SOCKET")
    if not addr:
        return
    if _notify_socket is None:
        _notify_socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    if addr.startswith("@"):
        addr = "\0" + addr[1:]
    try:
        _notify_socket.sendto(msg.encode(), addr)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Periodic maintenance
# ---------------------------------------------------------------------------


async def _periodic_maintenance():
    """Run maintenance tasks periodically."""
    while True:
        await asyncio.sleep(60)
        try:
            # Notify systemd watchdog
            _sd_notify("WATCHDOG=1")

            # Recover orphaned jobs every minute
            recovered = await db.recover_orphaned_jobs()
            if recovered:
                print(f"Recovered {recovered} orphaned job(s)")
        except Exception as e:
            print(f"Maintenance error (recovery): {e}")

        try:
            # Archive old jobs every hour (check modulo)
            import time
            if int(time.time()) % 3600 < 60:
                archived = await db.archive_old_jobs()
                if archived:
                    print(f"Auto-archived {archived} old job(s)")
        except Exception as e:
            print(f"Maintenance error (archive): {e}")

        try:
            # Clean up old screenshots
            await asyncio.to_thread(_cleanup_steer_snapshots)
        except Exception as e:
            print(f"Maintenance error (snapshots): {e}")


def _cleanup_steer_snapshots():
    """Clean up old screenshot snapshots from /tmp/steer."""
    steer_dir = Path(tempfile.gettempdir()) / "steer"
    if not steer_dir.is_dir():
        return
    import time
    cutoff = time.time() - 4 * 3600
    removed = 0
    pngs = sorted(steer_dir.glob("*.png"), key=lambda p: p.stat().st_mtime)
    for p in pngs:
        try:
            if p.stat().st_mtime < cutoff:
                p.unlink()
                removed += 1
        except OSError:
            pass
    remaining = sorted(steer_dir.glob("*.png"), key=lambda p: p.stat().st_mtime)
    while len(remaining) > 50:
        try:
            remaining.pop(0).unlink()
            removed += 1
        except OSError:
            pass
    if removed:
        print(f"Cleaned up {removed} stale screenshot(s)")


# ---------------------------------------------------------------------------
# Worker management
# ---------------------------------------------------------------------------


async def _spawn_worker(job_id: str, prompt: str):
    """Spawn a worker subprocess and track it."""
    worker_path = Path(__file__).parent / "worker.py"
    log_file = JOBS_DIR / f"{job_id}.log"
    log_fh = open(log_file, "w")

    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        str(worker_path),
        job_id,
        prompt,
        cwd=str(Path(__file__).parent),
        stdout=log_fh,
        stderr=log_fh,
        start_new_session=True,
    )

    # Update PID in DB
    await db.update_job(job_id, pid=proc.pid)
    _active_workers[job_id] = proc

    try:
        await proc.wait()
    finally:
        _active_workers.pop(job_id, None)
        _worker_semaphore.release()
        log_fh.close()
        # Trigger chain continuation
        asyncio.create_task(_submit_next_in_chain(job_id))


async def _submit_next_in_chain(job_id: str):
    """Check if a completed job has remaining chain steps and submit the next one."""
    try:
        job = await db.get_job(job_id)
        if not job or job.get("status") != "completed":
            return
        chain = job.get("chain", [])
        if not chain:
            return

        next_prompt = chain[0]
        remaining = chain[1:]

        prev_summary = job.get("summary", "")
        if prev_summary:
            contextualized_prompt = (
                f"This is a chained job. The previous job (ID: {job_id}) completed with this result:\n"
                f"---\n{prev_summary}\n---\n\n"
                f"Now do the following:\n{next_prompt}"
            )
        else:
            contextualized_prompt = next_prompt

        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.post(
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


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app):
    # Initialize database
    await db.init_db()
    await db.migrate_yaml_to_sqlite()
    recovered = await db.recover_orphaned_jobs()
    if recovered:
        print(f"Startup: recovered {recovered} orphaned job(s)")

    # Start cron scheduler
    cron_manager.start()

    # Start periodic maintenance
    maintenance_task = asyncio.create_task(_periodic_maintenance())

    # Tell systemd we're ready
    _sd_notify("READY=1")
    _sd_notify("WATCHDOG=1")

    yield

    # Shutdown
    maintenance_task.cancel()
    cron_manager.stop()
    await db.close_db()


app = FastAPI(lifespan=lifespan)


# ---------------------------------------------------------------------------
# Authentication middleware
# ---------------------------------------------------------------------------

_PUBLIC_PATHS = {"/auth/login", "/login", "/health"}
_LOCALHOST_PATHS = {"/job", "/jobs", "/cron", "/crons", "/reset", "/upload", "/api"}


def _is_localhost(request: Request) -> bool:
    client = request.client
    if not client:
        return False
    return client.host in ("127.0.0.1", "::1", "localhost")


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path

    if path in _PUBLIC_PATHS or path.startswith("/auth/"):
        return await call_next(request)

    if path.startswith("/uploads/"):
        return await call_next(request)

    # Localhost requests to API endpoints skip auth
    if _is_localhost(request) and any(path.startswith(p) for p in _LOCALHOST_PATHS):
        return await call_next(request)

    token = request.cookies.get(auth.SESSION_COOKIE)
    if token and auth.get_session_user(token):
        return await call_next(request)

    if path.startswith("/api/"):
        return JSONResponse(status_code=401, content={"detail": "Not authenticated"})
    return RedirectResponse(url="/login", status_code=302)


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
    username: str
    password: str


@app.get("/login", response_class=HTMLResponse)
async def login_page():
    login_file = Path(__file__).parent / "login.html"
    return await asyncio.to_thread(login_file.read_text)


@app.post("/auth/login")
async def login(req: LoginRequest, response: Response):
    if not auth.verify_password(req.username, req.password):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = auth.create_session(req.username)
    response = JSONResponse(content={"ok": True})
    response.set_cookie(
        key=auth.SESSION_COOKIE,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 30,
    )
    return response


@app.post("/auth/logout")
async def logout(request: Request):
    token = request.cookies.get(auth.SESSION_COOKIE)
    if token:
        auth.destroy_session(token)
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie(auth.SESSION_COOKIE)
    return response


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "workers_available": MAX_WORKERS - len(_active_workers),
        "workers_max": MAX_WORKERS,
        "active_jobs": list(_active_workers.keys()),
    }


# ---------------------------------------------------------------------------
# Job endpoints
# ---------------------------------------------------------------------------


class JobRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=MAX_PROMPT_LENGTH)
    chain: list[str] = Field(default_factory=list)
    chain_from: Optional[str] = None
    files: list[str] = Field(default_factory=list)
    submitted_by: Optional[str] = None


@app.post("/job")
async def create_job(req: JobRequest):
    if not _worker_semaphore._value > 0:
        raise HTTPException(
            status_code=429,
            detail=f"Too many concurrent jobs (max {MAX_WORKERS}). Try again later.",
        )
    await _worker_semaphore.acquire()

    job_id = uuid4().hex[:8]

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

    # Look up user info
    submitted_by = req.submitted_by
    user_email = None
    if submitted_by:
        user_info = auth.lookup_user(submitted_by)
        if user_info:
            user_email = user_info.get("email")
            submitted_by = user_info.get("display_name", submitted_by)

    await db.create_job(
        job_id=job_id,
        prompt=prompt,
        submitted_by=submitted_by,
        submitted_by_email=user_email,
        chain=req.chain if req.chain else None,
        chain_from=req.chain_from,
    )

    # Spawn worker as async task
    asyncio.create_task(_spawn_worker(job_id, prompt))

    return {"job_id": job_id, "status": "running"}


@app.get("/job/{job_id}")
async def get_job(job_id: str):
    """Get job as YAML (backward compat with telegram bot)."""
    job = await db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    # Convert updates from list of dicts to list of strings for compat
    if job.get("updates"):
        job["updates"] = [
            u["text"] if isinstance(u, dict) else u for u in job["updates"]
        ]
    # Remove internal fields
    job.pop("archived", None)
    return PlainTextResponse(
        yaml.dump(job, default_flow_style=False, sort_keys=False)
    )


@app.get("/jobs")
async def list_jobs_endpoint(archived: bool = False):
    """List all jobs as YAML."""
    jobs = await db.list_jobs(archived=archived)
    summary = []
    for j in jobs:
        summary.append({
            "id": j.get("id"),
            "status": j.get("status"),
            "prompt": j.get("prompt"),
            "created_at": j.get("created_at"),
        })
    return PlainTextResponse(
        yaml.dump({"jobs": summary}, default_flow_style=False, sort_keys=False)
    )


@app.post("/jobs/clear")
async def clear_jobs():
    count = await db.archive_all_jobs()
    return {"archived": count}


@app.delete("/job/{job_id}")
async def stop_job(job_id: str):
    job = await db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    pid = job.get("pid")
    if pid:
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError, OSError):
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass

    # Kill tmux session
    session_name = job.get("session", f"job-{job_id}")
    await asyncio.to_thread(
        subprocess.run,
        ["tmux", "kill-session", "-t", session_name],
        capture_output=True,
        check=False,
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    await db.update_job(job_id, status="stopped", completed_at=now)

    _active_workers.pop(job_id, None)

    return {"job_id": job_id, "status": "stopped"}


# ---------------------------------------------------------------------------
# Agent-facing endpoints (called by Claude agent via curl from tmux)
# ---------------------------------------------------------------------------


class UpdateRequest(BaseModel):
    text: str


class SummaryRequest(BaseModel):
    text: str


class AttachRequest(BaseModel):
    path: str


@app.post("/job/{job_id}/update")
async def job_update(job_id: str, req: UpdateRequest):
    """Append a progress update to a job."""
    job = await db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    await db.add_update(job_id, req.text)
    return {"ok": True}


@app.post("/job/{job_id}/summary")
async def job_summary(job_id: str, req: SummaryRequest):
    """Set the summary (response to user) for a job."""
    job = await db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    await db.set_summary(job_id, req.text)
    return {"ok": True}


@app.post("/job/{job_id}/attach")
async def job_attach(job_id: str, req: AttachRequest):
    """Add a file attachment to a job."""
    job = await db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    await db.add_attachment(job_id, req.path)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Cron endpoints (unchanged)
# ---------------------------------------------------------------------------


class CronRequest(BaseModel):
    name: str
    schedule: str
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
async def create_cron(req: CronRequest):
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
async def list_crons():
    return {"crons": cron_manager.list_crons()}


@app.get("/cron/{cron_id}")
async def get_cron(cron_id: str):
    cron = cron_manager.get_cron(cron_id)
    if not cron:
        raise HTTPException(status_code=404, detail="Cron not found")
    return cron


@app.put("/cron/{cron_id}")
async def update_cron(cron_id: str, req: CronUpdate):
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    cron = cron_manager.update_cron(cron_id, **updates)
    if not cron:
        raise HTTPException(status_code=404, detail="Cron not found")
    return cron


@app.delete("/cron/{cron_id}")
async def delete_cron(cron_id: str):
    if not cron_manager.delete_cron(cron_id):
        raise HTTPException(status_code=404, detail="Cron not found")
    return {"deleted": cron_id}


@app.post("/cron/{cron_id}/trigger")
async def trigger_cron(cron_id: str):
    if not cron_manager.trigger_cron(cron_id):
        raise HTTPException(status_code=404, detail="Cron not found")
    return {"triggered": cron_id}


# ---------------------------------------------------------------------------
# File upload
# ---------------------------------------------------------------------------


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 50MB)")
    ext = Path(file.filename or "file").suffix or ""
    unique_name = f"{uuid4().hex[:12]}{ext}"
    dest = UPLOAD_DIR / unique_name
    await asyncio.to_thread(dest.write_bytes, content)
    return {
        "filename": unique_name,
        "original_name": file.filename,
        "size": len(content),
        "path": str(dest),
    }


@app.get("/uploads/{filename}")
async def serve_upload(filename: str):
    filepath = UPLOAD_DIR / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(filepath)


# ---------------------------------------------------------------------------
# Dashboard API
# ---------------------------------------------------------------------------


@app.get("/api/job/{job_id}")
async def api_get_job(job_id: str):
    job = await db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    attachments = job.get("attachments", [])
    attachment_info = []
    for i, path in enumerate(attachments):
        p = Path(path)
        attachment_info.append({
            "index": i,
            "filename": p.name,
            "path": str(p),
            "exists": p.exists(),
            "is_image": p.suffix.lower()
            in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"},
            "url": f"/api/job/{job_id}/attachment/{i}",
        })
    updates = job.get("updates", [])
    if updates and isinstance(updates[0], dict):
        updates = [u.get("text", "") for u in updates]
    return {
        "id": job.get("id"),
        "status": job.get("status"),
        "summary": job.get("summary", ""),
        "updates": updates,
        "attachments": attachment_info,
        "created_at": job.get("created_at"),
        "completed_at": job.get("completed_at"),
    }


@app.get("/api/job/{job_id}/attachment/{index}")
async def serve_job_attachment(job_id: str, index: int):
    job = await db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    attachments = job.get("attachments", [])
    if index < 0 or index >= len(attachments):
        raise HTTPException(status_code=404, detail="Attachment not found")
    filepath = Path(attachments[index])
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")
    return FileResponse(filepath, filename=filepath.name)


@app.get("/api/me")
async def api_me(request: Request):
    token = request.cookies.get(auth.SESSION_COOKIE)
    username = auth.get_session_user(token) if token else None
    return {"username": username}


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    dashboard_file = Path(__file__).parent / "dashboard.html"
    if not dashboard_file.exists():
        raise HTTPException(status_code=404, detail="Dashboard not found")
    return await asyncio.to_thread(dashboard_file.read_text)


@app.get("/api/status")
async def api_status():
    jobs = await db.list_jobs(archived=False)

    active_jobs = []
    for data in jobs:
        raw_prompt = data.get("prompt") or ""
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
                "is_image": p.suffix.lower()
                in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"},
                "url": f"/api/job/{job_id}/attachment/{idx}",
            })

        updates = data.get("updates", [])
        if updates and isinstance(updates[0], dict):
            updates = [u.get("text", "") for u in updates]

        summary = data.get("summary") or ""
        active_jobs.append({
            "id": job_id,
            "status": data.get("status"),
            "prompt": (display_prompt[:200] + "...")
            if len(display_prompt) > 200
            else display_prompt,
            "created_at": data.get("created_at"),
            "completed_at": data.get("completed_at"),
            "duration_seconds": data.get("duration_seconds"),
            "summary": (summary[:300] + "...")
            if len(summary) > 300
            else summary,
            "updates": updates,
            "chain_from": data.get("chain_from"),
            "chain": data.get("chain", []),
            "attachments": attachment_info,
        })

    crons = cron_manager.list_crons()

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


# ---------------------------------------------------------------------------
# Reset endpoints
# ---------------------------------------------------------------------------


@app.post("/reset/soft")
async def soft_reset():
    results = {}

    # 1. Stop all running jobs
    jobs = await db.list_jobs()
    stopped = 0
    for j in jobs:
        if j.get("status") == "running":
            try:
                await stop_job(j["id"])
                stopped += 1
            except Exception:
                pass
    results["jobs_stopped"] = stopped

    # 2. Kill stale claude processes
    try:
        r = await asyncio.to_thread(
            subprocess.run,
            [
                "bash",
                "-c",
                """
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
            """,
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        results["processes_killed"] = int(r.stdout.strip() or "0")
    except Exception as e:
        results["processes_killed"] = f"error: {e}"

    # 3. Kill orphan tmux job sessions
    try:
        r = await asyncio.to_thread(
            subprocess.run,
            [
                "bash",
                "-c",
                """
            killed=0
            for session in $(tmux list-sessions -F '#{session_name}' 2>/dev/null | grep '^job-' || true); do
                job_id=${session#job-}
                killed=$((killed+1))
                tmux kill-session -t "$session" 2>/dev/null
            done
            echo "$killed"
            """,
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        results["sessions_killed"] = int(r.stdout.strip() or "0")
    except Exception as e:
        results["sessions_killed"] = f"error: {e}"

    # 4. Schedule service restart
    async def _restart_listen():
        await asyncio.sleep(1)
        await asyncio.to_thread(
            subprocess.run,
            ["sudo", "systemctl", "restart", "linux-agent-listen"],
            capture_output=True,
            timeout=15,
        )

    asyncio.create_task(_restart_listen())
    results["service_restart"] = "scheduled"

    return results


@app.post("/reset/hard")
async def hard_reset():
    async def _reboot():
        await asyncio.sleep(1)
        subprocess.Popen(
            ["sudo", "reboot"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    asyncio.create_task(_reboot())
    return {"status": "rebooting"}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    config = uvicorn.Config(app, host="0.0.0.0", port=7600)
    config.socket_options = [(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)]
    server = uvicorn.Server(config)
    server.run()
