"""API endpoints for CSV ingestion and data management."""
import logging
import tempfile
import shutil
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel

from services.ingest_service import scan_folder, ingest_files
from repos.cycles_repo import get_monthly_summary

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


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
def api_ingest(req: IngestRequest):
    """Ingest CSV files from local paths."""
    if not req.paths:
        raise HTTPException(400, "No paths provided")

    for p in req.paths:
        if not Path(p).exists():
            raise HTTPException(404, f"File not found: {p}")

    result = ingest_files(req.paths)
    return result


@router.post("/ingest/upload")
async def api_upload(files: list[UploadFile] = File(...)):
    """Upload and ingest CSV files."""
    if not files:
        raise HTTPException(400, "No files provided")

    tmp_dir = Path(tempfile.mkdtemp(prefix="dash_upload_"))
    saved_paths = []

    try:
        for upload_file in files:
            if not upload_file.filename:
                continue
            dest = tmp_dir / upload_file.filename
            with open(dest, "wb") as f:
                content = await upload_file.read()
                f.write(content)
            saved_paths.append(str(dest))

        result = ingest_files(saved_paths)
        return result
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@router.get("/ingest/status")
def api_ingest_status():
    """Get ingestion status summary."""
    return get_monthly_summary()
