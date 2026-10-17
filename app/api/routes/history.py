from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from app.api.dependencies import get_history
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


@router.get("/history", response_model=HistoryPage)
async def list_history(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    q: str | None = Query(None, max_length=200, description="Özet, kaynak adı veya türde arama"),
    document_type: str | None = Query(None, max_length=50),
    history: HistoryRepository = Depends(get_history),
):
    return history.list_records(limit=limit, offset=offset, query=q, document_type=document_type)


@router.get("/history/stats", response_model=HistoryStats)
async def history_stats(history: HistoryRepository = Depends(get_history)):
    return history.stats()


@router.get("/history/export-all", summary="Tüm analiz kayıtlarını JSON olarak indir")
async def export_all_records(history: HistoryRepository = Depends(get_history)):
    page = history.list_records(limit=10000, offset=0)
    records = []
    for item in page["items"]:
        full = history.get(item["id"])
        if full:
            records.append({**full.get("result", full), "review": full.get("review"), "id": item["id"]})
    return JSONResponse(
        content={"total": len(records), "records": records},
        headers={"Content-Disposition": 'attachment; filename="tum_analizler.json"'},
    )


@router.get("/history/{record_id}")
async def get_history_record(record_id: str, history: HistoryRepository = Depends(get_history)):
    return _require(history, record_id)


@router.patch("/history/{record_id}/review", response_model=ReviewState, summary="Memur onay kararını kaydet")
async def update_review(record_id: str, body: ReviewUpdate, history: HistoryRepository = Depends(get_history)):
    return history.update_review(record_id, body)


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
