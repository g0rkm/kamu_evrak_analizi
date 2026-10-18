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
        self._by_endpoint: dict[str, int] = defaultdict(int)
        self._started_at = time.monotonic()
        self._response_times: list[float] = []

    def record_request(self, status_code: int, endpoint: str = "", response_time: float = 0.0) -> None:
        with self._lock:
            self._requests += 1
            self._status_codes[status_code] += 1
            if status_code >= 400:
                self._errors += 1
            if endpoint:
                self._by_endpoint[endpoint] += 1
            if response_time > 0:
                self._response_times.append(response_time)

    def avg_response_time(self) -> float:
        """Ortalama yanıt süresini döndürür."""
        with self._lock:
            if not self._response_times:
                return 0.0
            return sum(self._response_times) / len(self._response_times)

    def endpoint_stats(self, endpoint: str) -> dict:
        """Belirli bir endpoint'in istatistiklerini döner."""
        with self._lock:
            count = self._by_endpoint.get(endpoint, 0)
            return {
                'endpoint': endpoint,
                'request_count': count,
                'percentage': round(count / self._requests * 100, 1) if self._requests > 0 else 0
            }

    def health_summary(self) -> dict:
        """Metrik sağlık özetini döner."""
        with self._lock:
            error_rate = self._errors / self._requests if self._requests > 0 else 0
            status = 'healthy' if error_rate < 0.05 else 'degraded' if error_rate < 0.2 else 'unhealthy'
            return {
                'status': status,
                'error_rate': round(error_rate, 4),
                'total_requests': self._requests,
                'total_errors': self._errors
            }

    def snapshot(self) -> dict:
        with self._lock:
            uptime = time.monotonic() - self._started_at
            rps = self._requests / uptime if uptime > 0 else 0
            avg_rt = (sum(self._response_times) / len(self._response_times)) if self._response_times else 0.0
            return {
                "total_requests": self._requests,
                "total_errors": self._errors,
                "error_rate": round(self._errors / self._requests, 4) if self._requests > 0 else 0,
                "requests_per_second": round(rps, 2),
                "status_codes": dict(self._status_codes),
                "top_endpoints": dict(sorted(self._by_endpoint.items(), key=lambda x: x[1], reverse=True)[:10]),
                "uptime_seconds": round(uptime, 1),
                "avg_response_time_ms": round(avg_rt, 1),
            }

    def error_rate(self) -> float:
        """Son isteklerin hata oranını döndürür (4xx + 5xx / toplam)."""
        with self._lock:
            if self._requests == 0:
                return 0.0
            return round(self._errors / self._requests, 4)

    def reset(self) -> None:
        with self._lock:
            self._requests = 0
            self._errors = 0
            self._status_codes.clear()
            self._by_endpoint.clear()
            self._started_at = time.monotonic()
            self._response_times = []


metrics = Metrics()
