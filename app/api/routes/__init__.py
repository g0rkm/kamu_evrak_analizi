from fastapi import APIRouter

from . import analysis, history, jobs, system, config_routes

router = APIRouter(prefix="/api")
router.include_router(analysis.router)
router.include_router(jobs.router)
router.include_router(history.router)
router.include_router(system.router)
router.include_router(config_routes.router)

__all__ = ["router"]
