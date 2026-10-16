from fastapi import Depends, Request

from app.container import ServiceContainer
from app.services.analysis_service import AnalysisService
from app.services.history_repository import HistoryRepository
from app.services.job_manager import JobManager
from app.services.upload_storage import UploadStorage


def get_container(request: Request) -> ServiceContainer:
    return request.app.state.container


def get_analysis_service(container: ServiceContainer = Depends(get_container)) -> AnalysisService:
    return container.analysis


def get_history(container: ServiceContainer = Depends(get_container)) -> HistoryRepository:
    return container.history


def get_storage(container: ServiceContainer = Depends(get_container)) -> UploadStorage:
    return container.storage


def get_jobs(container: ServiceContainer = Depends(get_container)) -> JobManager:
    return container.jobs
