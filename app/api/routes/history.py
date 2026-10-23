import csv
import io
import json as json_mod
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse, Response

from app.api.dependencies import get_container, get_history
from app.container import ServiceContainer
from app.core.exceptions import NotFoundError, InvalidInputError
from app.models.api import HistoryPage, HistoryStats
from app.models.review import ReviewState, ReviewUpdate
from app.services.history_repository import HistoryRepository
from app.services.export_service import ExportService
from pydantic import BaseModel

class BulkIdsBody(BaseModel):
    ids: list[str]

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


@router.get('/history/deleted', tags=['Gecmis'], summary='Silinen kayitlari listele')
async def list_deleted_records(request: Request, limit: int = 50, container = Depends(get_container)):
    records = container.history.deleted_records(limit=limit)
    return {'records': records, 'count': len(records)}


@router.get('/history/count', tags=['Gecmis'], summary='Toplam kayit sayisi')
async def record_count(request: Request, container: ServiceContainer = Depends(get_container)):
    all_records = container.history._load_all()
    total = len(all_records)
    active = len([r for r in all_records if not r.get('deleted')])
    deleted = total - active
    archived = len([r for r in all_records if r.get('archived') and not r.get('deleted')])
    return {'total': total, 'active': active, 'deleted': deleted, 'archived': archived}


@router.post("/history/search", tags=["Gecmis"])
async def full_text_search(request: Request, body: dict, container: ServiceContainer = Depends(get_container)):
    query = body.get("query", "").lower().strip()
    if not query:
        raise InvalidInputError("Arama sorgusu bos olamaz")
    fields = body.get("fields", ["summary", "source_name", "notes", "document_type"])
    limit = body.get("limit", 50)
    records = container.history._load_all()
    results = []
    for r in records:
        if r.get("deleted"):
            continue
        for field in fields:
            val = r.get(field, "")
            if isinstance(val, str) and query in val.lower():
                results.append(r)
                break
        if len(results) >= limit:
            break
    return {"results": results, "count": len(results), "query": query}


@router.get('/history/search-content', summary='İçerik bazlı arama')
async def search_content(keyword: str = Query(..., min_length=2), limit: int = Query(20, ge=1, le=100), container: ServiceContainer = Depends(get_container)):
    results = container.history.search_by_content(keyword, limit)
    return {'results': results, 'count': len(results), 'keyword': keyword}


@router.post('/history/advanced-search', tags=['Gecmis'], summary='Gelismis arama')
async def advanced_search(request: Request, body: dict, container: ServiceContainer = Depends(get_container)):
    records = container.history._load_all()
    records = [r for r in records if not r.get('deleted')]
    filters = body
    if filters.get('document_type'):
        records = [r for r in records if r.get('document_type', '').lower() == filters['document_type'].lower()]
    if filters.get('min_confidence') is not None:
        records = [r for r in records if r.get('confidence_score', 0) >= filters['min_confidence']]
    if filters.get('max_confidence') is not None:
        records = [r for r in records if r.get('confidence_score', 0) <= filters['max_confidence']]
    if filters.get('tags'):
        required_tags = set(filters['tags'])
        records = [r for r in records if required_tags.issubset(set(r.get('tags', [])))]
    if filters.get('keyword'):
        kw = filters['keyword'].lower()
        records = [r for r in records if kw in r.get('source_name', '').lower() or kw in r.get('summary', '').lower()]
    if filters.get('status'):
        records = [r for r in records if r.get('status') == filters['status']]
    limit = filters.get('limit', 50)
    return {'records': records[:limit], 'total_matches': len(records)}


@router.get("/history/stats", summary="Analiz istatistikleri")
async def history_stats(history: HistoryRepository = Depends(get_history)):
    return history.stats()


@router.get("/history/stats/daily", tags=["Gecmis"])
async def daily_stats(request: Request, days: int = 30, container: ServiceContainer = Depends(get_container)):
    from datetime import datetime, timedelta, timezone
    records = container.history._load_all()
    active = [r for r in records if not r.get("deleted")]
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    daily = {}
    for r in active:
        created = r.get("created_at", "")
        if created >= cutoff:
            day = created[:10]
            daily[day] = daily.get(day, 0) + 1
    sorted_days = sorted(daily.items())
    return {"daily_counts": [{"date": d, "count": c} for d, c in sorted_days], "total_days": len(sorted_days), "period_days": days}


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


@router.get('/history/summary-stats', tags=['Gecmis'], summary='Ozet istatistikler')
async def summary_statistics(request: Request, container: ServiceContainer = Depends(get_container)):
    records = container.history._load_all()
    records = [r for r in records if not r.get('deleted')]
    total = len(records)
    if not total:
        return {'total': 0, 'by_type': {}, 'avg_confidence': 0, 'date_range': None}
    by_type = {}
    confidences = []
    for r in records:
        dt = r.get('document_type', 'bilinmiyor')
        by_type[dt] = by_type.get(dt, 0) + 1
        c = r.get('confidence_score', 0)
        if c:
            confidences.append(c)
    avg_conf = sum(confidences)/len(confidences) if confidences else 0
    timestamps = [r.get('timestamp', '') for r in records if r.get('timestamp')]
    return {
        'total': total,
        'by_type': by_type,
        'avg_confidence': round(avg_conf, 4),
        'date_range': {
            'earliest': min(timestamps) if timestamps else None,
            'latest': max(timestamps) if timestamps else None
        }
    }


@router.get('/history/duplicates', tags=['Gecmis'], summary='Olasi duplike kayitlari bul')
async def find_duplicates(request: Request, container: ServiceContainer = Depends(get_container)):
    records = container.history._load_all()
    records = [r for r in records if not r.get('deleted')]
    seen = {}
    duplicates = []
    for r in records:
        key = (r.get('source_name', ''), r.get('document_type', ''))
        if key in seen:
            duplicates.append({
                'record_id': r.get('id'),
                'matches_with': seen[key],
                'source_name': key[0],
                'document_type': key[1]
            })
        else:
            seen[key] = r.get('id')
    return {'duplicates': duplicates, 'count': len(duplicates)}


@router.get('/history/by-type/{doc_type}', tags=['Gecmis'], summary='Ture gore kayitlar')
async def records_by_type(doc_type: str, request: Request, limit: int = 50, container: ServiceContainer = Depends(get_container)):
    records = container.history._load_all()
    filtered = [
        r for r in records
        if not r.get('deleted') and r.get('document_type', '').lower() == doc_type.lower()
    ][:limit]
    return {'records': filtered, 'count': len(filtered), 'document_type': doc_type}


@router.get("/history/by-priority/{priority}", tags=["Gecmis"])
async def records_by_priority(priority: str, request: Request, limit: int = 50, container: ServiceContainer = Depends(get_container)):
    valid = ["low", "normal", "high", "urgent"]
    if priority not in valid:
        raise InvalidInputError(f"Gecersiz oncelik: {priority}. Gecerli: {valid}")
    records = container.history._load_all()
    filtered = [r for r in records if not r.get("deleted") and r.get("priority", "normal") == priority][:limit]
    return {"records": filtered, "count": len(filtered), "priority": priority}


@router.get("/history/{record_id}/changelog", tags=["Gecmis"])
async def record_changelog(record_id: str, request: Request, container: ServiceContainer = Depends(get_container)):
    record = container.history.get(record_id)
    if not record:
        raise NotFoundError(f"Kayit bulunamadi: {record_id}")
    changelog = container.history.record_changelog(record_id)
    return {"record_id": record_id, "changelog": changelog, "count": len(changelog)}


@router.get('/history/tag-stats', tags=['Gecmis'], summary='Etiket istatistikleri')
async def tag_statistics(request: Request, container: ServiceContainer = Depends(get_container)):
    records = container.history._load_all()
    records = [r for r in records if not r.get('deleted')]
    tag_counts = {}
    for r in records:
        for tag in r.get('tags', []):
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
    sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)
    return {
        'tags': [{'tag': t, 'count': c} for t, c in sorted_tags],
        'total_unique_tags': len(tag_counts),
        'total_tag_usage': sum(tag_counts.values())
    }


@router.get('/history/favorites', tags=['Gecmis'], summary='Favori kayitlari listele')
async def list_favorites(request: Request, limit: int = 50, container: ServiceContainer = Depends(get_container)):
    records = container.history._load_all()
    favorites = [r for r in records if not r.get('deleted') and r.get('favorite')][:limit]
    return {'records': favorites, 'count': len(favorites)}


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


@router.get('/history/export-json', tags=['Gecmis'], summary='JSON olarak export')
async def export_json(request: Request, container: ServiceContainer = Depends(get_container)):
    records = container.history._load_all()
    records = [r for r in records if not r.get('deleted')]
    content = json_mod.dumps(records, ensure_ascii=False, indent=2)
    return Response(content=content, media_type='application/json', headers={'Content-Disposition': 'attachment; filename=export.json'})


@router.get("/history/export/csv", tags=["Gecmis"])
async def export_csv_endpoint(request: Request, container: ServiceContainer = Depends(get_container)):
    records = container.history._load_all()
    active = [r for r in records if not r.get("deleted")]
    csv_data = ExportService.to_csv(active)
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=kayitlar.csv"}
    )


@router.get("/history/export/json-file", tags=["Gecmis"])
async def export_json_file(request: Request, container: ServiceContainer = Depends(get_container)):
    records = container.history._load_all()
    active = [r for r in records if not r.get("deleted")]
    json_data = ExportService.to_json(active)
    return Response(
        content=json_data,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=kayitlar.json"}
    )


@router.get("/history/export/report", tags=["Gecmis"])
async def export_report(request: Request, container: ServiceContainer = Depends(get_container)):
    records = container.history._load_all()
    active = [r for r in records if not r.get("deleted")]
    report = ExportService.summary_report(active)
    return report


@router.get('/history/date-range', tags=['Gecmis'], summary='Tarih araliginda kayitlar')
async def records_by_date_range(request: Request, start: str = None, end: str = None, container: ServiceContainer = Depends(get_container)):
    records = container.history._load_all()
    records = [r for r in records if not r.get('deleted')]
    if start:
        records = [r for r in records if r.get('timestamp', '') >= start]
    if end:
        records = [r for r in records if r.get('timestamp', '') <= end]
    return {'records': records, 'count': len(records), 'date_range': {'start': start, 'end': end}}


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
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="gecmis.csv"'},
    )


@router.post("/history/bulk-delete", summary="Seçili kayıtları toplu sil")
async def bulk_delete_records(request: Request, body: dict, history: HistoryRepository = Depends(get_history)):
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
    audit = getattr(getattr(request.app.state, 'container', None), 'audit', None)
    if audit:
        audit.log('bulk_delete', details={'count': len(body.get('ids', []))})
    return {"deleted": deleted, "requested": len(ids)}


@router.post('/history/bulk-archive')
async def bulk_archive(request: Request, body: BulkIdsBody, container: ServiceContainer = Depends(get_container)):
    repo = container.history
    archived = 0
    for rid in body.ids:
        record = repo.get(rid)
        if record and not record.get('archived'):
            record['archived'] = True
            repo._write(rid, record)
            archived += 1
    audit = getattr(container, 'audit', None)
    if audit:
        audit.log('bulk_archive', details={'count': archived})
    return {'archived': archived}


@router.post('/history/bulk-export')
async def bulk_export(request: Request, body: BulkIdsBody, container: ServiceContainer = Depends(get_container)):
    records = [container.history.get(rid) for rid in body.ids]
    records = [r for r in records if r]
    return {'records': records, 'count': len(records)}


@router.post('/history/bulk-soft-delete', tags=['Gecmis'], summary='Toplu soft delete')
async def bulk_soft_delete(request: Request, body: BulkIdsBody, container: ServiceContainer = Depends(get_container)):
    repo = container.history
    deleted = 0
    for rid in body.ids:
        if repo.soft_delete(rid):
            deleted += 1
    audit = getattr(container, 'audit', None)
    if audit:
        audit.log('bulk_soft_delete', details={'count': deleted})
    return {'deleted': deleted, 'recoverable': True}


@router.post('/history/bulk-restore', tags=['Gecmis'], summary='Toplu geri yukleme')
async def bulk_restore(request: Request, body: BulkIdsBody, container: ServiceContainer = Depends(get_container)):
    repo = container.history
    restored = 0
    for rid in body.ids:
        if repo.restore_deleted(rid):
            restored += 1
    audit = getattr(container, 'audit', None)
    if audit:
        audit.log('bulk_restore', details={'count': restored})
    return {'restored': restored}


@router.post('/history/bulk-validate', tags=['Gecmis'], summary='Toplu kayit dogrulama')
async def bulk_validate(request: Request, body: BulkIdsBody, container: ServiceContainer = Depends(get_container)):
    results = []
    for rid in body.ids:
        record = container.history.get(rid)
        if not record:
            results.append({'record_id': rid, 'valid': False, 'issues': [{'field': 'id', 'issue': 'Kayit bulunamadi'}]})
            continue
        issues = []
        for f in ['id', 'file_name', 'status']:
            if not record.get(f):
                issues.append({'field': f, 'issue': 'Eksik'})
        results.append({'record_id': rid, 'valid': len(issues) == 0, 'issues': issues})
    return {'results': results, 'total': len(results), 'valid_count': sum(1 for r in results if r['valid'])}


@router.post("/history/bulk-priority", tags=["Gecmis"])
async def bulk_update_priority(request: Request, body: dict, container: ServiceContainer = Depends(get_container)):
    ids = body.get("ids", [])
    priority = body.get("priority", "normal")
    valid = ["low", "normal", "high", "urgent"]
    if priority not in valid:
        raise InvalidInputError(f"Gecersiz oncelik: {priority}")
    if not ids:
        raise InvalidInputError("ids listesi bos olamaz")
    updated = 0
    for rid in ids:
        record = container.history.get(rid)
        if record and not record.get("deleted"):
            container.history.update_field(rid, "priority", priority)
            updated += 1
    if container.audit:
        container.audit.log("bulk_priority", {"ids": ids, "priority": priority, "updated": updated})
    return {"updated": updated, "priority": priority}


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


@router.get('/history/{record_id}/report', tags=['Gecmis'], summary='Kayit raporu')
async def record_report(record_id: str, request: Request, container: ServiceContainer = Depends(get_container)):
    record = container.history.get(record_id)
    if not record:
        raise NotFoundError(f'{record_id} bulunamadi')
    result = record.get('result', {})
    analysis = result.get('analysis', {})
    classification = analysis.get('classification', {})
    return {
        'id': record_id,
        'file_name': record.get('source_name', record.get('file_name', '')),
        'document_type': record.get('document_type', classification.get('document_type', '')),
        'confidence': record.get('confidence_score', classification.get('confidence', 0)),
        'status': record.get('status', ''),
        'created_at': record.get('timestamp', ''),
        'summary': analysis.get('summary', record.get('summary', '')),
        'tags': record.get('tags', []),
        'notes': record.get('notes', ''),
        'favorite': record.get('favorite', False),
        'archived': record.get('archived', False),
        'processing_time': record.get('processing_time', 0)
    }


@router.get('/history/{record_id}/history', tags=['Gecmis'], summary='Kayit degisiklik gecmisi')
async def record_change_history(record_id: str, request: Request, container: ServiceContainer = Depends(get_container)):
    record = container.history.get(record_id)
    if not record:
        raise NotFoundError(f'{record_id} bulunamadi')
    audit = getattr(container, 'audit', None)
    changes = []
    if audit:
        logs = audit.get_logs(record_id=record_id)
        changes = [{
            'action': l.get('action'),
            'timestamp': l.get('timestamp'),
            'user': l.get('user', 'system'),
            'details': l.get('details')
        } for l in logs]
    return {'record_id': record_id, 'changes': changes, 'total_changes': len(changes)}


@router.post('/history/{record_id}/validate', tags=['Geçmiş'], summary='Kayıt geçerliliğini kontrol et')
async def validate_record(record_id: str, request: Request, container: ServiceContainer = Depends(get_container)):
    record = container.history.get(record_id)
    if not record:
        raise NotFoundError(f'{record_id} bulunamadı')
    issues = []
    required_fields = ['id', 'file_name', 'status', 'timestamp']
    for f in required_fields:
        if not record.get(f):
            issues.append({'field': f, 'issue': 'Eksik zorunlu alan'})
    cs = record.get('confidence_score')
    if cs is not None and not (0 <= cs <= 1):
        issues.append({'field': 'confidence_score', 'issue': 'Güven skoru 0-1 aralığında olmalı'})
    tags = record.get('tags', [])
    if tags and len(tags) > container.settings.MAX_TAGS_PER_RECORD:
        issues.append({'field': 'tags', 'issue': 'Etiket sınırı aşıldı'})
    return {'record_id': record_id, 'valid': len(issues) == 0, 'issues': issues}


@router.post('/history/{record_id}/clone', tags=['Gecmis'], summary='Kaydi kopyala')
async def clone_record(record_id: str, request: Request, container: ServiceContainer = Depends(get_container)):
    import uuid as uuid_mod
    record = container.history.get(record_id)
    if not record:
        raise NotFoundError(f'{record_id} bulunamadi')
    new_record = dict(record)
    new_id = f'clone_{uuid_mod.uuid4().hex[:8]}'
    new_record['id'] = new_id
    new_record['cloned_from'] = record_id
    container.history._write(new_id, new_record)
    audit = getattr(container, 'audit', None)
    if audit:
        audit.log('clone', record_id=new_id, details={'source': record_id})
    return {'id': new_id, 'cloned_from': record_id}


@router.delete('/history/{record_id}/soft', tags=['Gecmis'], summary='Kaydi soft delete yap')
async def soft_delete_record(record_id: str, request: Request, container = Depends(get_container)):
    repo = container.history
    if not repo.soft_delete(record_id):
        raise NotFoundError(f'{record_id} bulunamadi')
    audit = getattr(container, 'audit', None)
    if audit:
        audit.log('soft_delete', record_id=record_id)
    return {'status': 'deleted', 'record_id': record_id, 'recoverable': True}


@router.post('/history/{record_id}/restore', tags=['Gecmis'], summary='Silinen kaydi geri yukle')
async def restore_record(record_id: str, request: Request, container = Depends(get_container)):
    repo = container.history
    if not repo.restore_deleted(record_id):
        raise NotFoundError(f'{record_id} bulunamadi veya silinmemis')
    audit = getattr(container, 'audit', None)
    if audit:
        audit.log('restore', record_id=record_id)
    return {'status': 'restored', 'record_id': record_id}


@router.post('/history/{record_id}/archive', summary='Kaydi arsivle')
async def archive_record(request: Request, record_id: str, container: ServiceContainer = Depends(get_container)):
    record = container.history.get(record_id)
    if record is None:
        raise NotFoundError('Kayit bulunamadi.')
    container.history.update_field(record_id, 'archived', True)
    container.history.update_field(record_id, 'archived_at', datetime.now(timezone.utc).isoformat())
    audit = getattr(getattr(request.app.state, 'container', None), 'audit', None)
    if audit:
        audit.log('archive', record_id=record_id)
    return {'record_id': record_id, 'archived': True}


@router.post('/history/{record_id}/unarchive', summary='Kaydi arsivden cikar')
async def unarchive_record(request: Request, record_id: str, container: ServiceContainer = Depends(get_container)):
    record = container.history.get(record_id)
    if record is None:
        raise NotFoundError('Kayit bulunamadi.')
    container.history.update_field(record_id, 'archived', False)
    audit = getattr(getattr(request.app.state, 'container', None), 'audit', None)
    if audit:
        audit.log('unarchive', record_id=record_id)
    return {'record_id': record_id, 'archived': False}


@router.patch('/history/{record_id}/priority', tags=['Gecmis'])
async def update_priority(record_id: str, request: Request, body: dict, container: ServiceContainer = Depends(get_container)):
    priority = body.get('priority', 'normal')
    if priority not in ('low', 'normal', 'high', 'urgent'):
        return JSONResponse(status_code=400, content={'detail': 'Gecersiz oncelik: low, normal, high, urgent'})
    record = container.history.get(record_id)
    if not record:
        raise NotFoundError(f'{record_id} bulunamadi')
    container.history.update_field(record_id, 'priority', priority)
    audit = getattr(container, 'audit', None)
    if audit:
        audit.log('update_priority', record_id=record_id, details={'priority': priority})
    return {'record_id': record_id, 'priority': priority}


@router.get("/history/{record_id}")
async def get_history_record(record_id: str, history: HistoryRepository = Depends(get_history)):
    return _require(history, record_id)


@router.patch("/history/{record_id}/review", response_model=ReviewState, summary="Memur onay kararını kaydet")
async def update_review(record_id: str, body: ReviewUpdate, history: HistoryRepository = Depends(get_history)):
    return history.update_review(record_id, body)


@router.patch("/history/{record_id}/tags", summary="Kayıt etiketlerini güncelle")
async def update_tags(request: Request, record_id: str, body: dict, history: HistoryRepository = Depends(get_history), container: ServiceContainer = Depends(get_container)):
    record = _require(history, record_id)
    tags = body.get("tags")
    if len(tags) > container.settings.MAX_TAGS_PER_RECORD:
        from app.core.exceptions import InvalidInputError
        raise InvalidInputError(f'En fazla {container.settings.MAX_TAGS_PER_RECORD} etiket eklenebilir.')
    if any(len(t) > 50 for t in tags):
        from app.core.exceptions import InvalidInputError
        raise InvalidInputError('Etiket uzunlugu en fazla 50 karakter olabilir.')
    if not isinstance(tags, list):
        from app.core.exceptions import InvalidInputError
        raise InvalidInputError("'tags' bir liste olmalıdır.")
    if len(tags) > 10:
        from app.core.exceptions import InvalidInputError
        raise InvalidInputError("En fazla 10 etiket eklenebilir.")
    # Etiketleri normalize et
    tags = [str(t).strip().lower()[:50] for t in tags if str(t).strip()]
    history.update_tags(record_id, tags)
    audit = getattr(getattr(request.app.state, 'container', None), 'audit', None)
    if audit:
        audit.log('update_tags', record_id=record_id, details={'tags': tags})
    return {"record_id": record_id, "tags": tags}


@router.patch("/history/{record_id}/favorite", summary="Kayıdı favorilere ekle/çıkar")
async def toggle_favorite(request: Request, record_id: str, body: dict, history: HistoryRepository = Depends(get_history)):
    record = _require(history, record_id)
    favorite = body.get("favorite", False)
    history.update_field(record_id, "favorite", bool(favorite))
    audit = getattr(getattr(request.app.state, 'container', None), 'audit', None)
    if audit:
        audit.log('favorite', record_id=record_id)
    return {"record_id": record_id, "favorite": bool(favorite)}


@router.patch("/history/{record_id}/notes", summary="Kayıda not ekle")
async def update_notes(request: Request, record_id: str, body: dict, history: HistoryRepository = Depends(get_history), container: ServiceContainer = Depends(get_container)):
    record = _require(history, record_id)
    notes = body.get("notes", "")
    if len(notes) > container.settings.MAX_NOTE_LENGTH:
        from app.core.exceptions import InvalidInputError
        raise InvalidInputError(f'Not uzunlugu en fazla {container.settings.MAX_NOTE_LENGTH} karakter olabilir.')
    if not isinstance(notes, str):
        from app.core.exceptions import InvalidInputError
        raise InvalidInputError("'notes' bir metin olmalıdır.")
    history.update_field(record_id, "notes", notes)
    audit = getattr(getattr(request.app.state, 'container', None), 'audit', None)
    if audit:
        audit.log('update_notes', record_id=record_id)
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
async def delete_history_record(request: Request, record_id: str, history: HistoryRepository = Depends(get_history)):
    if not history.delete(record_id):
        raise NotFoundError("Analiz kaydı bulunamadı.")
    audit = getattr(getattr(request.app.state, 'container', None), 'audit', None)
    if audit:
        audit.log('delete', record_id=record_id)
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
async def import_records(request: Request, body: dict, container: ServiceContainer = Depends(get_container)):
    records = body.get("records")
    if not isinstance(records, list):
        from app.core.exceptions import InvalidInputError
        raise InvalidInputError("'records' listesi gereklidir.")
    if len(records) > 500:
        from app.core.exceptions import InvalidInputError
        raise InvalidInputError("Tek seferde en fazla 500 kayıt içe aktarılabilir.")
    imported = container.history.import_records(records)
    audit = getattr(getattr(request.app.state, 'container', None), 'audit', None)
    if audit:
        audit.log('import_records', details={'count': len(records)})
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
