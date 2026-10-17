"""Basit bellek-içi istek/hata metrikleri. Harici bağımlılık gerektirmez."""
from __future__ import annotations

import threading
import time
from collections import defaultdict


class Metrics:
    """Thread-safe istek ve hata sayaçları."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._requests = 0
        self._errors = 0
        self._status_codes: dict[int, int] = defaultdict(int)
        self._started_at = time.monotonic()

    def record_request(self, status_code: int) -> None:
        with self._lock:
            self._requests += 1
            self._status_codes[status_code] += 1
            if status_code >= 400:
                self._errors += 1

    def snapshot(self) -> dict:
        with self._lock:
            uptime = time.monotonic() - self._started_at
            rps = self._requests / uptime if uptime > 0 else 0
            return {
                "total_requests": self._requests,
                "total_errors": self._errors,
                "error_rate": round(self._errors / self._requests, 4) if self._requests > 0 else 0,
                "requests_per_second": round(rps, 2),
                "status_codes": dict(self._status_codes),
                "uptime_seconds": round(uptime, 1),
            }

    def reset(self) -> None:
        with self._lock:
            self._requests = 0
            self._errors = 0
            self._status_codes.clear()
            self._started_at = time.monotonic()


metrics = Metrics()
