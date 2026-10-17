import csv
import io

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from app.api.dependencies import get_container, get_history
from app.container import ServiceContainer
from app.core.exceptions import NotFoundError
from app.models.api import HistoryPage, HistoryStats
from app.models.review import ReviewState, ReviewUpdate
from app.services.history_repository import HistoryRepository

router = APIRouter(tags=["geçmiş"])


def _require(history: HistoryRepository, record_id: str) -> dict:
    record = history.get(record_id)
    if record is None:
        raise NotFoundError("Analiz kaydı bulunamadı.")
    return record


@router.get("/history", summary="Analiz geçmişi listele")
async def list_history(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    q: str | None = Query(None, max_length=200, description="Özet, kaynak adı veya türde arama"),
    document_type: str | None = Query(None, max_length=50),
    draft_status: str | None = Query(None, max_length=20, description="Taslak durumuna göre filtrele"),
    sort: str | None = Query(None, max_length=30, description="Sıralama: newest, oldest, confidence_desc, confidence_asc"),
    date_from: str | None = Query(None, max_length=10, description="Başlangıç tarihi (YYYY-MM-DD)"),
    date_to: str | None = Query(None, max_length=10, description="Bitiş tarihi (YYYY-MM-DD)"),
    min_confidence: float | None = Query(None, ge=0, le=100, description="Minimum güven skoru filtresi"),
    favorite: bool | None = Query(None, description="Sadece favorileri göster"),
    history: HistoryRepository = Depends(get_history),
):
    result = history.list_records(limit=limit, offset=offset, query=q, document_type=document_type, draft_status=draft_status, sort=sort, date_from=date_from, date_to=date_to, min_confidence=min_confidence, favorite=favorite)
    result["has_more"] = (offset + limit) < result["total"]
    result["offset"] = offset
    result["limit"] = limit
    return result


@router.get("/history/stats", response_model=HistoryStats)
async def history_stats(history: HistoryRepository = Depends(get_history)):
    return history.stats()


@router.get("/history/trends", summary="Günlük analiz trend verisi")
async def history_trends(
    days: int = Query(30, ge=1, le=365, description="Kaç günlük trend"),
    history: HistoryRepository = Depends(get_history),
):
    """Son N gündeki günlük analiz sayılarını döndürür."""
    from collections import Counter
    from datetime import datetime, timedelta, timezone
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    page = history.list_records(limit=10000, offset=0, date_from=cutoff[:10])
    daily = Counter()
    for item in page["items"]:
        date_str = item["timestamp"][:10]
        daily[date_str] += 1
    # Son N gün için sıralı liste
    result = []
    today = datetime.now(timezone.utc).date()
    for i in range(days):
        d = (today - timedelta(days=days - 1 - i)).isoformat()
        result.append({"date": d, "count": daily.get(d, 0)})
    return {"days": days, "trends": result}


@router.get("/history/export-all", summary="Tüm analiz kayıtlarını JSON olarak indir")
async def export_all_records(history: HistoryRepository = Depends(get_history)):
    page = history.list_records(limit=10000, offset=0)
    records = []
    for item in page["items"]:
        full = history.get(item["id"])
        if full:
            records.append({**full.get("result", full), "review": full.get("review"), "tags": full.get("tags", []), "id": item["id"]})
    return JSONResponse(
        content={"total": len(records), "records": records},
        headers={"Content-Disposition": 'attachment; filename="tum_analizler.json"'},
    )


@router.delete("/history/clear", summary="Tüm analiz kayıtlarını sil")
async def clear_all_records(history: HistoryRepository = Depends(get_history)):
    deleted = history.clear_all()
    return {"deleted": deleted}


@router.get("/history/export-csv", summary="Analiz kayıtlarını CSV olarak indir")
async def export_csv(history: HistoryRepository = Depends(get_history)):
    page = history.list_records(limit=10000, offset=0)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "timestamp", "source_name", "document_type", "confidence_score", "processing_time", "status", "draft_status", "tags"])
    for item in page["items"]:
        writer.writerow([
            item["id"],
            item["timestamp"],
            item["source_name"],
            item["document_type"],
            item.get("confidence_score", 0),
            item.get("processing_time", 0),
            item.get("status", ""),
            item.get("draft_status", "pending"),
            ",".join(item.get("tags", [])),
        ])
    from starlette.responses import Response
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="gecmis.csv"'},
    )


@router.post("/history/bulk-delete", summary="Seçili kayıtları toplu sil")
async def bulk_delete_records(body: dict, history: HistoryRepository = Depends(get_history)):
    ids = body.get("ids")
    if not isinstance(ids, list) or not ids:
        from app.core.exceptions import InvalidInputError
        raise InvalidInputError("'ids' listesi gereklidir.")
    if len(ids) > 100:
        from app.core.exceptions import InvalidInputError
        raise InvalidInputError("Tek seferde en fazla 100 kayıt silinebilir.")
    deleted = 0
    for record_id in ids:
        if history.delete(record_id):
            deleted += 1
    return {"deleted": deleted, "requested": len(ids)}


@router.get("/history/{record_id}")
async def get_history_record(record_id: str, history: HistoryRepository = Depends(get_history)):
    return _require(history, record_id)


@router.patch("/history/{record_id}/review", response_model=ReviewState, summary="Memur onay kararını kaydet")
async def update_review(record_id: str, body: ReviewUpdate, history: HistoryRepository = Depends(get_history)):
    return history.update_review(record_id, body)


@router.patch("/history/{record_id}/tags", summary="Kayıt etiketlerini güncelle")
async def update_tags(record_id: str, body: dict, history: HistoryRepository = Depends(get_history)):
    record = _require(history, record_id)
    tags = body.get("tags")
    if not isinstance(tags, list):
        from app.core.exceptions import InvalidInputError
        raise InvalidInputError("'tags' bir liste olmalıdır.")
    if len(tags) > 10:
        from app.core.exceptions import InvalidInputError
        raise InvalidInputError("En fazla 10 etiket eklenebilir.")
    # Etiketleri normalize et
    tags = [str(t).strip().lower()[:50] for t in tags if str(t).strip()]
    history.update_tags(record_id, tags)
    return {"record_id": record_id, "tags": tags}


@router.patch("/history/{record_id}/favorite", summary="Kayıdı favorilere ekle/çıkar")
async def toggle_favorite(record_id: str, body: dict, history: HistoryRepository = Depends(get_history)):
    record = _require(history, record_id)
    favorite = body.get("favorite", False)
    history.update_field(record_id, "favorite", bool(favorite))
    return {"record_id": record_id, "favorite": bool(favorite)}


@router.patch("/history/{record_id}/notes", summary="Kayıda not ekle")
async def update_notes(record_id: str, body: dict, history: HistoryRepository = Depends(get_history)):
    record = _require(history, record_id)
    notes = body.get("notes", "")
    if not isinstance(notes, str):
        from app.core.exceptions import InvalidInputError
        raise InvalidInputError("'notes' bir metin olmalıdır.")
    if len(notes) > 2000:
        from app.core.exceptions import InvalidInputError
        raise InvalidInputError("Not en fazla 2000 karakter olabilir.")
    history.update_field(record_id, "notes", notes)
    return {"record_id": record_id, "notes": notes}


@router.delete("/history/{record_id}")
async def delete_history_record(record_id: str, history: HistoryRepository = Depends(get_history)):
    if not history.delete(record_id):
        raise NotFoundError("Analiz kaydı bulunamadı.")
    return {"status": "deleted"}


@router.get("/export/{record_id}", summary="Analiz sonucunu JSON olarak indir")
async def export_result(record_id: str, history: HistoryRepository = Depends(get_history)):
    record = _require(history, record_id)
    content = {**record.get("result", record), "review": record.get("review")}
    return JSONResponse(
        content=content,
        headers={"Content-Disposition": f'attachment; filename="analiz_{record_id}.json"'},
    )


@router.get("/history/{record_id}/audit", summary="Denetim kaydını getir")
async def get_audit_log(record_id: str, history: HistoryRepository = Depends(get_history)):
    record = _require(history, record_id)
    review = record.get("review") or {}
    return {"record_id": record_id, "audit_log": review.get("audit_log", [])}


@router.post("/history/import", summary="Dışa aktarılmış kayıtları içe aktar")
async def import_records(body: dict, container: ServiceContainer = Depends(get_container)):
    records = body.get("records")
    if not isinstance(records, list):
        from app.core.exceptions import InvalidInputError
        raise InvalidInputError("'records' listesi gereklidir.")
    if len(records) > 500:
        from app.core.exceptions import InvalidInputError
        raise InvalidInputError("Tek seferde en fazla 500 kayıt içe aktarılabilir.")
    imported = container.history.import_records(records)
    return {"imported": imported}
