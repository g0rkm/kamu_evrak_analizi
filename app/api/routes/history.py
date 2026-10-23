import csv
import io
from datetime import datetime, timezone

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
    has_notes: bool | None = Query(None, description="Not içeren kayıtları filtrele"),
    history: HistoryRepository = Depends(get_history),
):
    result = history.list_records(limit=limit, offset=offset, query=q, document_type=document_type, draft_status=draft_status, sort=sort, date_from=date_from, date_to=date_to, min_confidence=min_confidence, favorite=favorite, has_notes=has_notes)
    result["has_more"] = (offset + limit) < result["total"]
    result["offset"] = offset
    result["limit"] = limit
    return result


@router.get('/history/recent', summary='Son analizler')
async def recent_analyses(count: int = Query(5, ge=1, le=20), container: ServiceContainer = Depends(get_container)):
    records = container.history.recent_records(count)
    return {'records': records, 'count': len(records)}


@router.get('/history/archived', summary='Arsivlenmis kayitlar')
async def list_archived(limit: int = Query(50, ge=1, le=200), container: ServiceContainer = Depends(get_container)):
    records = container.history.archived_records(limit)
    return {'records': records, 'count': len(records)}


@router.get("/history/search", summary="Gelişmiş geçmiş arama")
async def search_history(
    q: str = Query("", min_length=1),
    document_type: str = Query(None),
    date_from: str = Query(None),
    date_to: str = Query(None),
    min_confidence: float = Query(None, ge=0, le=1),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    container: ServiceContainer = Depends(get_container),
):
    results = container.history.list_records(
        limit=limit,
        offset=offset,
        query=q,
        document_type=document_type,
        date_from=date_from,
        date_to=date_to,
        min_confidence=min_confidence,
    )
    return results


@router.get('/history/search-content', summary='İçerik bazlı arama')
async def search_content(keyword: str = Query(..., min_length=2), limit: int = Query(20, ge=1, le=100), container: ServiceContainer = Depends(get_container)):
    results = container.history.search_by_content(keyword, limit)
    return {'results': results, 'count': len(results), 'keyword': keyword}


@router.get("/history/stats", summary="Analiz istatistikleri")
async def history_stats(history: HistoryRepository = Depends(get_history)):
    return history.stats()


@router.get('/history/processing-time-stats', summary='İşlem süresi istatistikleri')
async def processing_time_stats(container: ServiceContainer = Depends(get_container)):
    stats = container.history.stats()
    return {
        'avg_processing_time': stats.get('avg_processing_time', 0),
        'min_processing_time': stats.get('min_processing_time', 0),
        'max_processing_time': stats.get('max_processing_time', 0),
        'total_records': stats.get('total', 0)
    }


@router.get('/history/status-distribution', summary='Taslak durum dagilimi')
async def status_distribution(container: ServiceContainer = Depends(get_container)):
    distribution = container.history.count_by_status()
    return {'distribution': distribution, 'total': sum(distribution.values())}


@router.get('/history/confidence-distribution', summary='Guven skoru dagilimi')
async def confidence_distribution(container: ServiceContainer = Depends(get_container)):
    items = container.history.list_records(limit=10000)['items']
    buckets = {'0-20': 0, '20-40': 0, '40-60': 0, '60-80': 0, '80-100': 0}
    for item in items:
        score = item.get('confidence_score', 0) * 100
        if score < 20:
            buckets['0-20'] += 1
        elif score < 40:
            buckets['20-40'] += 1
        elif score < 60:
            buckets['40-60'] += 1
        elif score < 80:
            buckets['60-80'] += 1
        else:
            buckets['80-100'] += 1
    return {'distribution': buckets, 'total': sum(buckets.values())}


@router.get('/history/statistics/daily', summary='Gunluk analiz istatistikleri')
async def daily_statistics(days: int = Query(7, ge=1, le=90), container: ServiceContainer = Depends(get_container)):
    from datetime import datetime, timedelta, timezone
    items = container.history.list_records(limit=10000)['items']
    daily = {}
    today = datetime.now(timezone.utc).date()
    for i in range(days):
        day = (today - timedelta(days=i)).isoformat()
        daily[day] = 0
    for item in items:
        ts = item.get('timestamp', '')[:10]
        if ts in daily:
            daily[ts] += 1
    sorted_days = sorted(daily.items())
    return {'days': [{'date': d, 'count': c} for d, c in sorted_days], 'total_days': len(sorted_days)}


@router.get("/history/types", summary="Belge turlerini listele")
async def list_document_types(container: ServiceContainer = Depends(get_container)):
    stats = container.history.stats()
    by_type = stats.get("by_type", {})
    types = [{"type": t, "count": c} for t, c in sorted(by_type.items(), key=lambda x: x[1], reverse=True)]
    return {"types": types, "total_types": len(types)}


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


@router.get('/history/timeline', summary='Zaman cigizi gorunumu')
async def history_timeline(limit: int = Query(50, ge=1, le=200), container: ServiceContainer = Depends(get_container)):
    items = container.history.list_records(limit=limit)['items']
    timeline = []
    for item in items:
        timeline.append({
            'id': item['id'],
            'timestamp': item.get('timestamp', ''),
            'source_name': item.get('source_name', ''),
            'document_type': item.get('document_type', ''),
            'confidence_score': item.get('confidence_score', 0),
            'status': item.get('status', '')
        })
    return {'timeline': timeline, 'count': len(timeline)}


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


@router.get('/history/export-filtered', summary='Filtrelenmis gecmis verisi')
async def export_filtered(
    document_type: str = Query(None),
    date_from: str = Query(None),
    date_to: str = Query(None),
    favorite: bool = Query(None),
    container: ServiceContainer = Depends(get_container),
):
    records = container.history.export_filtered(document_type=document_type, date_from=date_from, date_to=date_to, favorite=favorite)
    return {'records': records, 'count': len(records)}


@router.get('/history/compare/{id1}/{id2}', summary='Iki kaydi karsilastir')
async def compare_records(id1: str, id2: str, container: ServiceContainer = Depends(get_container)):
    rec1 = container.history.get(id1)
    rec2 = container.history.get(id2)
    if rec1 is None or rec2 is None:
        raise NotFoundError('Kayit bulunamadi.')
    return {
        'record_1': {
            'id': id1,
            'source_name': rec1.get('source_name', ''),
            'document_type': rec1.get('document_type', ''),
            'confidence_score': rec1.get('confidence_score', 0)
        },
        'record_2': {
            'id': id2,
            'source_name': rec2.get('source_name', ''),
            'document_type': rec2.get('document_type', ''),
            'confidence_score': rec2.get('confidence_score', 0)
        },
        'same_type': rec1.get('document_type') == rec2.get('document_type'),
        'confidence_diff': round(abs(rec1.get('confidence_score', 0) - rec2.get('confidence_score', 0)), 2)
    }


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


@router.patch('/history/bulk-tags', summary='Toplu etiket guncelleme')
async def bulk_update_tags(body: dict, container: ServiceContainer = Depends(get_container)):
    ids = body.get('ids', [])
    tags = body.get('tags', [])
    if not ids or len(ids) > 100:
        from app.core.exceptions import InvalidInputError
        raise InvalidInputError('ids listesi 1-100 arasi olmalidir.')
    if not isinstance(tags, list):
        from app.core.exceptions import InvalidInputError
        raise InvalidInputError('tags bir liste olmalidir.')
    updated = 0
    for record_id in ids:
        try:
            container.history.update_tags(record_id, tags)
            updated += 1
        except Exception:
            pass
    return {'updated': updated, 'total': len(ids)}


@router.get('/history/{record_id}/related', summary='Iliskili kayitlar')
async def related_records(record_id: str, limit: int = Query(5, ge=1, le=20), container: ServiceContainer = Depends(get_container)):
    record = container.history.get(record_id)
    if record is None:
        raise NotFoundError('Kayit bulunamadi.')
    doc_type = record.get('document_type', '')
    items = container.history.list_records(limit=limit + 1, document_type=doc_type)['items']
    related = [i for i in items if i['id'] != record_id][:limit]
    return {'record_id': record_id, 'document_type': doc_type, 'related': related, 'count': len(related)}


@router.post('/history/{record_id}/archive', summary='Kaydi arsivle')
async def archive_record(record_id: str, container: ServiceContainer = Depends(get_container)):
    record = container.history.get(record_id)
    if record is None:
        raise NotFoundError('Kayit bulunamadi.')
    container.history.update_field(record_id, 'archived', True)
    container.history.update_field(record_id, 'archived_at', datetime.now(timezone.utc).isoformat())
    return {'record_id': record_id, 'archived': True}


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


@router.post("/history/{record_id}/duplicate", summary="Analiz kaydını kopyala")
async def duplicate_record(record_id: str, history: HistoryRepository = Depends(get_history)):
    record = _require(history, record_id)
    # Kopyayı kaydet
    new_record = {k: v for k, v in record.items() if k not in ("id", "review")}
    new_record["source_name"] = f"{record.get('source_name', 'Kopya')} (kopya)"
    new_id = history.save(new_record)
    return {"original_id": record_id, "new_id": new_id}


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


@router.get("/history/{record_id}/audit", summary="Kayıt denetim geçmişi")
async def get_audit_log(record_id: str, container: ServiceContainer = Depends(get_container)):
    record = container.history.get(record_id)
    if record is None:
        raise NotFoundError("Analiz kaydı bulunamadı.")
    review = record.get("review", {})
    audit_log = review.get("audit_log", [])
    return {"record_id": record_id, "audit_log": audit_log, "total_entries": len(audit_log)}


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


@router.patch('/history/bulk-favorite', summary='Toplu favori guncelleme')
async def bulk_toggle_favorite(body: dict, container: ServiceContainer = Depends(get_container)):
    ids = body.get('ids', [])
    favorite = body.get('favorite', True)
    if not ids or len(ids) > 100:
        from app.core.exceptions import InvalidInputError
        raise InvalidInputError('ids listesi 1-100 arasi olmalidir.')
    updated = 0
    for record_id in ids:
        try:
            container.history.update_field(record_id, 'favorite', favorite)
            updated += 1
        except Exception:
            pass
    return {'updated': updated, 'total': len(ids), 'favorite': favorite}
