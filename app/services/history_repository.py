"""JSON dosya tabanlı analiz geçmişi deposu (repository deseni)."""
from __future__ import annotations

import json
import os
import re
import threading
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from app.core.exceptions import NotFoundError
from app.models.review import ReviewState, ReviewUpdate


class HistoryRepository:
    """Her analiz sonucu `<id>.json` dosyası olarak saklanır."""

    _ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
    SUMMARY_PREVIEW_CHARS = 160

    def __init__(self, directory: Path, max_records: int = 10000) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self._max_records = max_records
        self._lock = threading.Lock()

    # ── Yazma ─────────────────────────────────────────────

    def save(self, result: dict) -> str:
        # Kayıt sayısı limitini kontrol et
        max_records = self._max_records
        existing = list(self.directory.glob("*.json"))
        if len(existing) >= max_records:
            # En eski kaydı sil
            oldest = min(existing, key=lambda p: p.stat().st_mtime)
            oldest.unlink()

        now = datetime.now(timezone.utc)
        record_id = f"{now.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        analysis = result.get("analysis") or {}
        record = {
            "id": record_id,
            "timestamp": now.isoformat(),
            "source_name": result.get("source_name", ""),
            "document_type": (analysis.get("classification") or {}).get("document_type", "bilinmiyor"),
            "confidence_score": result.get("confidence_score", 0),
            "processing_time": result.get("processing_time", 0),
            "status": result.get("status", "completed"),
            "summary": analysis.get("summary", ""),
            "review": ReviewState().model_dump(mode="json"),
            "result": result,
        }
        self._write(record_id, record)
        return record_id

    def update_review(self, record_id: str, update: ReviewUpdate) -> ReviewState:
        with self._lock:
            record = self.get(record_id)
            if record is None:
                raise NotFoundError("Analiz kaydı bulunamadı.")
            current = ReviewState.model_validate(record.get("review") or {})
            changes = update.model_dump(exclude_unset=True)
            review = current.model_copy(update={**changes, "updated_at": datetime.now(timezone.utc)})
            audit_entry = {
                "action": next((k for k in changes if k.endswith("_status")), "update"),
                "changes": changes,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            review = review.model_copy(update={"audit_log": [*current.audit_log, audit_entry]})
            record["review"] = review.model_dump(mode="json")
            self._write(record_id, record, locked=True)
        return review

    def update_tags(self, record_id: str, tags: list[str]) -> None:
        """Kayıt etiketlerini günceller."""
        path = self.directory / f"{record_id}.json"
        if not path.exists():
            raise NotFoundError("Analiz kaydı bulunamadı.")
        with self._lock:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            data["tags"] = tags
            with path.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

    def update_field(self, record_id: str, field: str, value) -> None:
        """Kayıttaki belirli bir alanı günceller."""
        path = self.directory / f"{record_id}.json"
        if not path.exists():
            raise NotFoundError("Analiz kaydı bulunamadı.")
        with self._lock:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            data[field] = value
            with path.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

    def delete(self, record_id: str) -> bool:
        path = self._path(record_id)
        with self._lock:
            if not path.exists():
                return False
            path.unlink()
            return True

    def clear_all(self) -> int:
        """Tüm kayıtları siler, silinen kayıt sayısını döndürür."""
        count = 0
        with self._lock:
            for path in list(self.directory.glob("*.json")):
                try:
                    path.unlink()
                    count += 1
                except OSError:
                    pass
        return count

    def import_records(self, records: list[dict]) -> int:
        """Dışa aktarılmış kayıtları içe aktarır. Mevcut ID'ler güncellenir."""
        imported = 0
        for record in records:
            record_id = record.get("id")
            if not record_id or not self._ID_PATTERN.match(record_id):
                continue
            self._write(record_id, record)
            imported += 1
        return imported

    # ── Okuma ─────────────────────────────────────────────

    def get(self, record_id: str) -> dict | None:
        path = self._path(record_id)
        if not path.exists():
            return None
        try:
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

    def list_records(self, limit: int = 50, offset: int = 0, query: str | None = None, document_type: str | None = None, draft_status: str | None = None, sort: str | None = None, date_from: str | None = None, date_to: str | None = None, min_confidence: float | None = None, favorite: bool | None = None, has_notes: bool | None = None) -> dict:
        items = self._summaries()
        if document_type:
            items = [i for i in items if i["document_type"] == document_type]
        if draft_status:
            items = [i for i in items if i["draft_status"] == draft_status]
        if query:
            needle = query.casefold()
            items = [
                i for i in items
                if needle in i["summary"].casefold()
                or needle in i["source_name"].casefold()
                or needle in i["document_type"].casefold()
                or needle in (i.get("keywords") or "").casefold()
                or needle in " ".join(i.get("tags") or []).casefold()
            ]
        if date_from:
            items = [i for i in items if i.get("timestamp", "") >= date_from]
        if date_to:
            items = [i for i in items if i.get("timestamp", "")[:10] <= date_to]
        if min_confidence is not None:
            items = [i for i in items if i.get("confidence_score", 0) >= min_confidence]
        if favorite is not None:
            items = [i for i in items if i.get("favorite", False) == favorite]
        if has_notes is not None:
            items = [i for i in items if bool(i.get("notes", "")) == has_notes]
        if sort == "oldest":
            items.sort(key=lambda i: i["timestamp"])
        elif sort == "confidence_desc":
            items.sort(key=lambda i: i["confidence_score"], reverse=True)
        elif sort == "confidence_asc":
            items.sort(key=lambda i: i["confidence_score"])
        # "newest" veya None = varsayılan (dosya adına göre ters sıralı, zaten öyle)
        return {"total": len(items), "items": items[offset: offset + limit]}

    def stats(self) -> dict:
        items = self._summaries()
        total = len(items)
        if total == 0:
            return {"total": 0, "avg_confidence": 0, "avg_processing_time": 0, "by_type": {}, "by_draft_status": {}, "favorites_count": 0}
        confidences = [i["confidence_score"] for i in items]
        times = [i["processing_time"] for i in items]
        return {
            "total": total,
            "avg_confidence": round(sum(confidences) / total, 2),
            "min_confidence": round(min(confidences), 2),
            "max_confidence": round(max(confidences), 2),
            "avg_processing_time": round(sum(times) / total, 2),
            "min_processing_time": round(min(times), 2),
            "max_processing_time": round(max(times), 2),
            "by_type": dict(Counter(i["document_type"] for i in items).most_common()),
            "by_draft_status": dict(Counter(i["draft_status"] for i in items)),
            "favorites_count": sum(1 for i in items if i.get("favorite", False)),
        }

    # ── Yardımcılar ───────────────────────────────────────

    def _summaries(self) -> list[dict]:
        summaries = []
        for path in sorted(self.directory.glob("*.json"), reverse=True):
            try:
                with path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue
            summaries.append({
                "id": data.get("id", path.stem),
                "timestamp": data.get("timestamp", ""),
                "source_name": data.get("source_name", "") or "",
                "document_type": data.get("document_type", "") or "",
                "confidence_score": float(data.get("confidence_score", 0) or 0),
                "processing_time": float(data.get("processing_time", 0) or 0),
                "status": data.get("status", ""),
                "summary": (data.get("summary", "") or "")[: self.SUMMARY_PREVIEW_CHARS],
                "draft_status": (data.get("review") or {}).get("draft_status", "pending"),
                "keywords": ", ".join((((data.get("result") or {}).get("analysis") or {}).get("content") or {}).get("keywords") or []),
                "favorite": data.get("favorite", False),
                "tags": data.get("tags", []),
                "notes": data.get("notes", ""),
            })
        return summaries

    def _path(self, record_id: str) -> Path:
        if not self._ID_PATTERN.match(record_id or ""):
            raise NotFoundError("Analiz kaydı bulunamadı.")
        return self.directory / f"{record_id}.json"

    def _write(self, record_id: str, record: dict, locked: bool = False) -> None:
        """Yarım yazılmış dosya kalmaması için geçici dosyaya yazıp yerine taşır."""
        path = self._path(record_id)
        tmp = path.with_suffix(".json.tmp")

        def write() -> None:
            with tmp.open("w", encoding="utf-8") as f:
                json.dump(record, f, ensure_ascii=False, indent=2, default=str)
            os.replace(tmp, path)

        if locked:
            write()
        else:
            with self._lock:
                write()
