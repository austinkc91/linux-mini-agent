import os
import shutil
import signal
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import yaml
from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from typing import Optional

import cron_manager

app = FastAPI()

JOBS_DIR = Path(__file__).parent / "jobs"
JOBS_DIR.mkdir(exist_ok=True)
ARCHIVED_DIR = JOBS_DIR / "archived"


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
            with open(f, "w") as fh:
                yaml.dump(data, fh, default_flow_style=False, sort_keys=False)
            print(f"Recovered orphaned job: {data.get('id')}")
        except Exception as e:
            print(f"Error recovering job {f.name}: {e}")


@app.on_event("startup")
def startup_recovery():
    _recover_orphaned_jobs()
    cron_manager.start()


@app.on_event("shutdown")
def shutdown_scheduler():
    cron_manager.stop()


class JobRequest(BaseModel):
    prompt: str


@app.post("/job")
def create_job(req: JobRequest):
    job_id = uuid4().hex[:8]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    job_data = {
        "id": job_id,
        "status": "running",
        "prompt": req.prompt,
        "created_at": now,
        "pid": 0,
        "updates": [],
        "summary": "",
        "attachments": [],
    }

    # Write YAML before spawning worker (worker reads it on startup)
    job_file = JOBS_DIR / f"{job_id}.yaml"
    with open(job_file, "w") as f:
        yaml.dump(job_data, f, default_flow_style=False, sort_keys=False)

    # Spawn the worker process (in its own process group for clean shutdown)
    worker_path = Path(__file__).parent / "worker.py"
    log_file = JOBS_DIR / f"{job_id}.log"
    log_fh = open(log_file, "w")
    proc = subprocess.Popen(
        [sys.executable, str(worker_path), job_id, req.prompt],
        cwd=str(Path(__file__).parent),
        stdout=log_fh,
        stderr=log_fh,
        start_new_session=True,
    )

    # Update PID after spawn
    job_data["pid"] = proc.pid
    with open(job_file, "w") as f:
        yaml.dump(job_data, f, default_flow_style=False, sort_keys=False)

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
    with open(job_file, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)

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


if __name__ == "__main__":
    import socket
    import uvicorn

    # Enable SO_REUSEADDR so restarts don't fail with "address already in use"
    config = uvicorn.Config(app, host="0.0.0.0", port=7600)
    config.socket_options = [(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)]
    server = uvicorn.Server(config)
    server.run()
