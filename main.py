"""FastAPI app for day_viewer - Daily roll data viewer with expected filtering."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers.cycles import router as cycles_router
from routers.ingest import router as ingest_router
from routers.settings import router as settings_router
from services.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
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
