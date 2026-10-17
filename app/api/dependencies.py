from fastapi import Depends, Header, Request

from app.container import ServiceContainer
from app.core.exceptions import AppError
from app.services.analysis_service import AnalysisService
from app.services.history_repository import HistoryRepository
from app.services.job_manager import JobManager
from app.services.upload_storage import UploadStorage


class UnauthorizedError(AppError):
    status_code = 401
    code = "unauthorized"
    default_message = "Yetkilendirme başarısız."


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


def require_admin(
    authorization: str | None = Header(None),
    container: ServiceContainer = Depends(get_container),
):
    """Admin token kontrolü. ADMIN_TOKEN boşsa kontrol atlanır."""
    token = container.settings.ADMIN_TOKEN
    if not token:
        return  # Token yapılandırılmamış, kontrol atlanır
    if not authorization or authorization != f"Bearer {token}":
        raise UnauthorizedError("Geçersiz veya eksik yetkilendirme token'ı.")
