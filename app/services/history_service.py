"""JSON dosya tabanli analiz gecmisi servisi."""
import json
import os
import uuid
from datetime import datetime

from app.config import get_settings


class HistoryService:
    """Analiz sonuclarini JSON dosyalari olarak saklar."""

    def __init__(self):
        settings = get_settings()
        self.history_dir = settings.HISTORY_DIR
        os.makedirs(self.history_dir, exist_ok=True)

    def save(self, result: dict) -> str:
        """Analiz sonucunu kaydet, ID dondur."""
        record_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
        record = {
            "id": record_id,
            "timestamp": datetime.now().isoformat(),
            "document_type": result.get("analysis", {}).get("classification", {}).get("document_type", "bilinmiyor"),
            "confidence_score": result.get("confidence_score", 0),
            "processing_time": result.get("processing_time", 0),
            "status": result.get("status", "completed"),
            "summary": result.get("analysis", {}).get("summary", ""),
            "result": result,
        }
        file_path = os.path.join(self.history_dir, f"{record_id}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
        return record_id

    def list_all(self, limit: int = 50, offset: int = 0) -> dict:
        """Tum gecmis kayitlarini listele (ozet bilgi)."""
        files = []
        if os.path.exists(self.history_dir):
            files = [f for f in os.listdir(self.history_dir) if f.endswith(".json")]
        files.sort(reverse=True)

        total = len(files)
        page_files = files[offset:offset + limit]

        items = []
        for fname in page_files:
            fpath = os.path.join(self.history_dir, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                items.append({
                    "id": data.get("id", fname.replace(".json", "")),
                    "timestamp": data.get("timestamp", ""),
                    "document_type": data.get("document_type", ""),
                    "confidence_score": data.get("confidence_score", 0),
                    "processing_time": data.get("processing_time", 0),
                    "status": data.get("status", ""),
                    "summary": (data.get("summary", "") or "")[:120],
                })
            except (json.JSONDecodeError, OSError):
                continue

        return {"total": total, "items": items}

    def get(self, record_id: str) -> dict | None:
        """Belirli bir analiz sonucunu getir."""
        file_path = os.path.join(self.history_dir, f"{record_id}.json")
        if not os.path.exists(file_path):
            return None
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_stats(self) -> dict:
        """Istatistik ozeti dondur."""
        listing = self.list_all(limit=9999)
        items = listing["items"]
        total = len(items)
        if total == 0:
            return {"total": 0, "avg_confidence": 0, "avg_processing_time": 0, "by_type": {}}

        avg_confidence = sum(i["confidence_score"] for i in items) / total
        avg_time = sum(i["processing_time"] for i in items) / total

        by_type = {}
        for item in items:
            dt = item["document_type"]
            by_type[dt] = by_type.get(dt, 0) + 1

        return {
            "total": total,
            "avg_confidence": round(avg_confidence, 2),
            "avg_processing_time": round(avg_time, 2),
            "by_type": by_type,
        }

    def delete(self, record_id: str) -> bool:
        """Bir kaydi sil."""
        file_path = os.path.join(self.history_dir, f"{record_id}.json")
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
        return False
