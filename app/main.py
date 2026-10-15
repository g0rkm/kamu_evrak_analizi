import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.api.routes import router

app = FastAPI(
    title="Kamu Evrak Analizi Sistemi",
    description="Kamu evrak ve yazışma süreçleri için akıllı agent destek sistemi",
    version="1.0.0"
)

app.include_router(router)

# Frontend static dosyaları
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

@app.get("/")
async def root():
    """Ana sayfa - frontend index.html döndür."""
    index_path = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Kamu Evrak Analizi API", "docs": "/docs"}
