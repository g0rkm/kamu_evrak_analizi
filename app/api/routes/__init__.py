from fastapi import APIRouter

from . import analysis, history, jobs, system

router = APIRouter(prefix="/api")
router.include_router(analysis.router)
router.include_router(jobs.router)
router.include_router(history.router)
router.include_router(system.router)

__all__ = ["router"]
