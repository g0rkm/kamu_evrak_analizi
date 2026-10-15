import os
import shutil
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, HTTPException
from app.agents.orchestrator import OrchestratorAgent
from app.config import get_settings

router = APIRouter(prefix="/api", tags=["evrak"])

@router.post("/analyze")
async def analyze_document(file: UploadFile = File(...)):
    """Evrak yükle ve uçtan uca analiz et."""
    settings = get_settings()
    
    # Dosya uzantısı kontrolü
    allowed_extensions = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".txt", ".md"}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail=f"Desteklenmeyen dosya türü: {ext}")
    
    # Dosya boyutu kontrolü
    content = await file.read()
    if len(content) > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Dosya boyutu çok büyük")
    
    # Geçici dosyaya kaydet
    upload_dir = settings.UPLOAD_DIR
    os.makedirs(upload_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_filename = f"{timestamp}_{file.filename}"
    file_path = os.path.join(upload_dir, safe_filename)
    
    with open(file_path, "wb") as f:
        f.write(content)
    
    # Pipeline çalıştır
    orchestrator = OrchestratorAgent()
    try:
        result = await orchestrator.execute(file_path=file_path)
        return result.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await orchestrator.close()

@router.post("/analyze-text")
async def analyze_text(body: dict):
    """Düz metin olarak evrak analiz et (dosya yüklemeden)."""
    text = body.get("text", "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Metin boş olamaz")
    
    # Geçici metin dosyası oluştur
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
        return result.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await orchestrator.close()

@router.get("/health")
async def health_check():
    """Sistem sağlık kontrolü."""
    return {"status": "ok", "service": "Kamu Evrak Analizi Sistemi"}
