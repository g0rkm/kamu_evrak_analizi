"""Uzun süren analizleri arka planda çalıştıran, ilerlemesi izlenebilen iş yöneticisi.

İstemci işi başlatır, `job_id` alır ve `/api/jobs/{id}` ile adım adım ilerlemeyi
sorgular. Böylece tarayıcı tarafında HTTP zaman aşımı yaşanmaz ve kullanıcı
gerçek pipeline durumunu görür.
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Awaitable, Callable

from app.agents.orchestrator import PIPELINE_STEPS, PipelineObserver
from app.core.exceptions import AppError, NotFoundError
from app.models.draft import StepTiming

logger = logging.getLogger("job_manager")

JobRunner = Callable[[PipelineObserver], Awaitable[dict]]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class StepProgress:
    key: str
    label: str
    status: str = "pending"
    duration: float | None = None


@dataclass
class Job(PipelineObserver):
    id: str
    source_name: str
    status: str = "queued"
    steps: list[StepProgress] = field(default_factory=lambda: [StepProgress(s.key, s.label) for s in PIPELINE_STEPS])
    result: dict | None = None
    error: dict | None = None
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    created_monotonic: float = field(default_factory=time.monotonic)

    # PipelineObserver
    def on_step_started(self, step_key: str) -> None:
        self._update(step_key, status="running")

    def on_step_finished(self, timing: StepTiming) -> None:
        self._update(timing.step, status=timing.status, duration=timing.duration)

    def _update(self, step_key: str, **changes) -> None:
        for step in self.steps:
            if step.key == step_key:
                for name, value in changes.items():
                    setattr(step, name, value)
        self.updated_at = _now()

    @property
    def finished(self) -> bool:
        return self.status in ("completed", "failed")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "status": self.status,
            "source_name": self.source_name,
            "steps": [vars(s) for s in self.steps],
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class JobManager:
    def __init__(self, max_concurrent: int = 2, ttl_seconds: int = 3600) -> None:
        self._jobs: dict[str, Job] = {}
        self._tasks: set[asyncio.Task] = set()
        self._semaphore = asyncio.Semaphore(max(1, max_concurrent))
        self.ttl_seconds = ttl_seconds

    def submit(self, source_name: str, runner: JobRunner) -> Job:
        self._purge_expired()
        job = Job(id=uuid.uuid4().hex, source_name=source_name)
        self._jobs[job.id] = job
        task = asyncio.create_task(self._run(job, runner), name=f"job-{job.id}")
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return job

    def get(self, job_id: str) -> Job:
        job = self._jobs.get(job_id)
        if job is None:
            raise NotFoundError("İş bulunamadı veya süresi doldu.")
        return job

    async def shutdown(self, grace_period: float = 15.0) -> None:
        """Açık işlerin tamamlanmasını bekler; süre aşılırsa iptal eder."""
        if not self._tasks:
            return
        logger.info("Kapatma: %d açık iş bekleniyor (maks %.0f sn)", len(self._tasks), grace_period)
        done, pending = await asyncio.wait(self._tasks, timeout=grace_period)
        if pending:
            logger.warning("Kapatma: %d iş süre aşımından iptal ediliyor", len(pending))
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
        logger.info("Kapatma: tüm işler sonlandı")

    async def _run(self, job: Job, runner: JobRunner) -> None:
        async with self._semaphore:
            job.status = "running"
            job.updated_at = _now()
            try:
                job.result = await runner(job)
                job.status = "completed"
            except AppError as exc:
                job.error = {"code": exc.code, "detail": exc.message}
                job.status = "failed"
            except asyncio.CancelledError:
                job.error = {"code": "cancelled", "detail": "İşlem iptal edildi."}
                job.status = "failed"
                raise
            except Exception:
                logger.exception("Analiz işi beklenmeyen bir hatayla sonlandı (%s)", job.id)
                job.error = {"code": "internal_error", "detail": "Analiz sırasında beklenmeyen bir hata oluştu."}
                job.status = "failed"
            finally:
                for step in job.steps:
                    if step.status in ("pending", "running") and job.status == "failed":
                        step.status = "skipped"
                job.updated_at = _now()

    def _purge_expired(self) -> None:
        cutoff = time.monotonic() - self.ttl_seconds
        for job_id in [j.id for j in self._jobs.values() if j.finished and j.created_monotonic < cutoff]:
            del self._jobs[job_id]
