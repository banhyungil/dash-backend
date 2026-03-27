"""FastAPI app for day_viewer - Daily roll data viewer with expected filtering."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from routers.cycles import router as cycles_router
from routers.ingest import router as ingest_router
from routers.settings import router as settings_router
from services.database import seed_settings


def _run_migrations():
    """Alembic 마이그레이션을 최신까지 자동 적용."""
    from alembic.config import Config
    from alembic import command
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _run_migrations()
    seed_settings()
    yield


app = FastAPI(title="Day Viewer API", version="1.0.0", lifespan=lifespan)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# GZip 압축 — 파형 데이터 등 대용량 JSON 응답 압축
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Include routers
app.include_router(cycles_router)
app.include_router(ingest_router)
app.include_router(settings_router)


@app.get("/")
def root():
    return {
        "message": "Day Viewer API - Daily roll data viewer with expected filtering",
        "docs": "/docs",
    }


# 직접 실행 시 uvicorm으로 실행
# # 환경변수 읽어서 설정
if __name__ == "__main__":
    import os
    import uvicorn
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("main:app", host=host, port=port, reload=True)
