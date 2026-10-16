import os
import shutil
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from app.agents.orchestrator import OrchestratorAgent
from app.config import get_settings
from app.services.history_service import HistoryService

router = APIRouter(prefix="/api", tags=["evrak"])
history_service = HistoryService()


@router.post("/analyze")
async def analyze_document(file: UploadFile = File(...)):
    """Evrak yukle ve uctan uca analiz et."""
    settings = get_settings()

    allowed_extensions = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".txt", ".md"}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail=f"Desteklenmeyen dosya turu: {ext}")

    content = await file.read()
    if len(content) > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Dosya boyutu cok buyuk")

    upload_dir = settings.UPLOAD_DIR
    os.makedirs(upload_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_filename = f"{timestamp}_{file.filename}"
    file_path = os.path.join(upload_dir, safe_filename)

    with open(file_path, "wb") as f:
        f.write(content)

    orchestrator = OrchestratorAgent()
    try:
        result = await orchestrator.execute(file_path=file_path)
        result_dict = result.model_dump()
        record_id = history_service.save(result_dict)
        result_dict["history_id"] = record_id
        return result_dict
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await orchestrator.close()


@router.post("/analyze-text")
async def analyze_text(body: dict):
    """Duz metin olarak evrak analiz et."""
    text = body.get("text", "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Metin bos olamaz")

    settings = get_settings()
    upload_dir = settings.UPLOAD_DIR
    os.makedirs(upload_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = os.path.join(upload_dir, f"{timestamp}_metin.txt")

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(text)

    orchestrator = OrchestratorAgent()
    try:
        result = await orchestrator.execute(file_path=file_path)
        result_dict = result.model_dump()
        record_id = history_service.save(result_dict)
        result_dict["history_id"] = record_id
        return result_dict
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await orchestrator.close()


@router.get("/history")
async def list_history(limit: int = 50, offset: int = 0):
    """Analiz gecmisini listele."""
    return history_service.list_all(limit=limit, offset=offset)


@router.get("/history/stats")
async def history_stats():
    """Analiz istatistiklerini dondur."""
    return history_service.get_stats()


@router.get("/history/{record_id}")
async def get_history_record(record_id: str):
    """Belirli bir analiz kaydini getir."""
    record = history_service.get(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Kayit bulunamadi")
    return record


@router.delete("/history/{record_id}")
async def delete_history_record(record_id: str):
    """Bir analiz kaydini sil."""
    if history_service.delete(record_id):
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Kayit bulunamadi")


@router.get("/export/{record_id}")
async def export_result(record_id: str):
    """Analiz sonucunu JSON olarak indir."""
    record = history_service.get(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Kayit bulunamadi")
    return JSONResponse(
        content=record.get("result", record),
        headers={"Content-Disposition": f"attachment; filename=analiz_{record_id}.json"},
    )


@router.get("/health")
async def health_check():
    """Sistem saglik kontrolu."""
    return {"status": "ok", "service": "Kamu Evrak Analizi Sistemi"}
