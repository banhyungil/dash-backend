"""FastAPI app for day_viewer - Daily roll data viewer with expected filtering."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers.data_router import router as data_router

app = FastAPI(title="Day Viewer API", version="1.0.0")

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


@app.get("/")
def root():
    return {
        "message": "Day Viewer API - Daily roll data viewer with expected filtering",
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
