"""Arka plan analiz işleri: arayüz bu uç noktalarla gerçek zamanlı ilerleme gösterir."""
from fastapi import APIRouter, Depends, File, UploadFile, status

from app.api.dependencies import get_analysis_service, get_jobs, get_storage
from app.models.api import JobCreated, JobStatusResponse, TextAnalysisRequest
from app.services.analysis_service import AnalysisService
from app.services.job_manager import JobManager
from app.services.upload_storage import UploadStorage

router = APIRouter(prefix="/jobs", tags=["işler"])


@router.post("/text", response_model=JobCreated, status_code=status.HTTP_202_ACCEPTED)
async def create_text_job(
    body: TextAnalysisRequest,
    service: AnalysisService = Depends(get_analysis_service),
    jobs: JobManager = Depends(get_jobs),
):
    text = service.validate_text(body.text)  # Hatalı girdiyi iş kuyruğa girmeden reddet
    title = (body.title or "").strip() or service.default_title(text)
    job = jobs.submit(title, lambda observer: service.analyze_text(text, title, observer))
    return JobCreated(job_id=job.id)


@router.post("/file", response_model=JobCreated, status_code=status.HTTP_202_ACCEPTED)
async def create_file_job(
    file: UploadFile = File(...),
    storage: UploadStorage = Depends(get_storage),
    service: AnalysisService = Depends(get_analysis_service),
    jobs: JobManager = Depends(get_jobs),
):
    stored = await storage.save(file)
    job = jobs.submit(stored.original_name, lambda observer: service.analyze_file(stored, observer))
    return JobCreated(job_id=job.id)


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job(job_id: str, jobs: JobManager = Depends(get_jobs)):
    return jobs.get(job_id).to_dict()
