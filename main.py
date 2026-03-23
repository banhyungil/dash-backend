"""FastAPI app for day_viewer - Daily roll data viewer with expected filtering."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers.data_router import router as data_router
from routers.ingest_router import router as ingest_router
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
app.include_router(data_router)
app.include_router(ingest_router)


@app.get("/")
def root():
    return {
        "message": "Day Viewer API - Daily roll data viewer with expected filtering",
        "docs": "/docs",
    }
