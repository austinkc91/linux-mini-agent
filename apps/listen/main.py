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

app = FastAPI()

JOBS_DIR = Path(__file__).parent / "jobs"
JOBS_DIR.mkdir(exist_ok=True)
ARCHIVED_DIR = JOBS_DIR / "archived"


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
    }

    # Write YAML before spawning worker (worker reads it on startup)
    job_file = JOBS_DIR / f"{job_id}.yaml"
    with open(job_file, "w") as f:
        yaml.dump(job_data, f, default_flow_style=False, sort_keys=False)

    # Spawn the worker process
    worker_path = Path(__file__).parent / "worker.py"
    proc = subprocess.Popen(
        [sys.executable, str(worker_path), job_id, req.prompt],
        cwd=str(Path(__file__).parent),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
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
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass

    data["status"] = "stopped"
    with open(job_file, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    return {"job_id": job_id, "status": "stopped"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7600)
