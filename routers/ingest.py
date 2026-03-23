"""API endpoints for CSV ingestion and data management."""
import logging
import tempfile
import shutil
import uuid
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from pydantic import BaseModel

from services.ingest_service import scan_folder, ingest_file
from repos.cycles_repo import get_monthly_summary

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

# ---------------------------------------------------------------------------
# In-memory job tracker
# ---------------------------------------------------------------------------
_jobs: dict[str, dict] = {}


def _run_ingest_job(job_id: str, paths: list[str]):
    """Background task: ingest files and update job status."""
    job = _jobs[job_id]
    job["status"] = "running"
    job["total_files"] = len(paths)

    total_files = 0
    success_cycles = 0
    skipped_cycles = 0
    failed_lines = 0
    details = []

    for i, p in enumerate(paths):
        result = ingest_file(p)
        details.append(result)
        total_files += 1
        success_cycles += result["cycles_ingested"]
        skipped_cycles += result["cycles_skipped"]
        failed_lines += len(result["errors"])

        job["completed_files"] = i + 1
        job["success_cycles"] = success_cycles

    job["status"] = "done"
    job["result"] = {
        "total_files": total_files,
        "success_cycles": success_cycles,
        "skipped_cycles": skipped_cycles,
        "failed_lines": failed_lines,
        "details": details,
    }


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class ScanRequest(BaseModel):
    folder: str


class IngestRequest(BaseModel):
    paths: list[str]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/ingest/scan")
def api_scan(req: ScanRequest):
    """Scan a local folder for PULSE/VIB CSV files."""
    folder = req.folder.strip()
    if not Path(folder).exists():
        raise HTTPException(404, f"Folder not found: {folder}")

    files = scan_folder(folder)
    return {"folder": folder, "files": files}


@router.post("/ingest")
def api_ingest(req: IngestRequest, background_tasks: BackgroundTasks):
    """Start async ingestion of CSV files. Returns job_id for progress tracking."""
    if not req.paths:
        raise HTTPException(400, "No paths provided")

    for p in req.paths:
        if not Path(p).exists():
            raise HTTPException(404, f"File not found: {p}")

    job_id = str(uuid.uuid4())[:8]
    _jobs[job_id] = {
        "status": "queued",
        "total_files": len(req.paths),
        "completed_files": 0,
        "success_cycles": 0,
        "result": None,
    }

    background_tasks.add_task(_run_ingest_job, job_id, req.paths)

    return {"job_id": job_id, "status": "queued", "total_files": len(req.paths)}


@router.get("/ingest/job/{job_id}")
def api_job_status(job_id: str):
    """Get ingestion job progress."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, f"Job not found: {job_id}")
    return job


@router.post("/ingest/upload")
async def api_upload(files: list[UploadFile] = File(...), background_tasks: BackgroundTasks = None):
    """Upload and ingest CSV files."""
    if not files:
        raise HTTPException(400, "No files provided")

    tmp_dir = Path(tempfile.mkdtemp(prefix="dash_upload_"))
    saved_paths = []

    for upload_file in files:
        if not upload_file.filename:
            continue
        dest = tmp_dir / upload_file.filename
        with open(dest, "wb") as f:
            content = await upload_file.read()
            f.write(content)
        saved_paths.append(str(dest))

    job_id = str(uuid.uuid4())[:8]
    _jobs[job_id] = {
        "status": "queued",
        "total_files": len(saved_paths),
        "completed_files": 0,
        "success_cycles": 0,
        "result": None,
        "_tmp_dir": str(tmp_dir),
    }

    def _run_upload_job():
        try:
            _run_ingest_job(job_id, saved_paths)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    background_tasks.add_task(_run_upload_job)

    return {"job_id": job_id, "status": "queued", "total_files": len(saved_paths)}


@router.get("/ingest/status")
def api_ingest_status():
    """Get ingestion status summary."""
    return get_monthly_summary()
