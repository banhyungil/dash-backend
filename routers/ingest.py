"""CSV 적재 및 데이터 관리 API."""
import logging
import tempfile
import shutil
import uuid
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from pydantic import BaseModel

from services.ingest_service import scan_folder, ingest_files
from repos.cycles_repo import get_monthly_summary

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

# ---------------------------------------------------------------------------
# 잡 상태 관리 (인메모리)
# ---------------------------------------------------------------------------
_jobs: dict[str, dict] = {}


def _run_ingest_job(job_id: str, paths: list[str]):
    """백그라운드 적재: 서비스에 콜백 전달하여 프로그레스 업데이트."""
    job = _jobs[job_id]
    job["status"] = "running"

    def on_progress(completed: int, total: int):
        job["completed_files"] = completed

    result = ingest_files(paths, on_progress=on_progress)

    job["status"] = "done"
    job["success_cycles"] = result["success_cycles"]
    job["result"] = result


# ---------------------------------------------------------------------------
# 요청 모델
# ---------------------------------------------------------------------------

class ScanRequest(BaseModel):
    folder: str


class IngestRequest(BaseModel):
    paths: list[str]


# ---------------------------------------------------------------------------
# 엔드포인트
# ---------------------------------------------------------------------------

@router.post("/ingest/scan")
def scan(req: ScanRequest):
    """로컬 폴더에서 PULSE/VIB CSV 파일 스캔."""
    folder = req.folder.strip()
    if not Path(folder).exists():
        raise HTTPException(404, f"Folder not found: {folder}")

    files = scan_folder(folder)
    return {"folder": folder, "files": files}


@router.post("/ingest")
def ingest(req: IngestRequest, background_tasks: BackgroundTasks):
    """CSV 파일 비동기 적재. job_id를 반환하여 진행 상태 추적 가능."""
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
def get_job_status(job_id: str):
    """적재 잡 진행 상태 조회."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, f"Job not found: {job_id}")
    return job


@router.post("/ingest/upload")
async def upload(files: list[UploadFile] = File(...), background_tasks: BackgroundTasks = None):
    """CSV 파일 업로드 후 비동기 적재."""
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
    }

    def _run_upload_job():
        try:
            _run_ingest_job(job_id, saved_paths)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    background_tasks.add_task(_run_upload_job)

    return {"job_id": job_id, "status": "queued", "total_files": len(saved_paths)}


@router.get("/ingest/status")
def get_status():
    """적재 현황 요약 조회."""
    return get_monthly_summary()
