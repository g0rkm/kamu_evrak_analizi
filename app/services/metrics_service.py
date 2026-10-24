import threading, time
from typing import Any
from collections import defaultdict

class MetricsService:
    """API kullanım ve performans metrikleri."""
    
    def __init__(self):
        self._lock = threading.Lock()
        self._endpoint_counts: dict[str, int] = defaultdict(int)
        self._endpoint_times: dict[str, list[float]] = defaultdict(list)
        self._status_counts: dict[int, int] = defaultdict(int)
        self._error_count = 0
        self._total_requests = 0
        self._start_time = time.time()
    
    def record_request(self, method: str, path: str, status_code: int, duration_ms: float):
        with self._lock:
            key = f"{method} {path}"
            self._endpoint_counts[key] += 1
            self._endpoint_times[key].append(duration_ms)
            # Son 1000 kaydı tut (bellek koruması)
            if len(self._endpoint_times[key]) > 1000:
                self._endpoint_times[key] = self._endpoint_times[key][-1000:]
            self._status_counts[status_code] += 1
            self._total_requests += 1
            if status_code >= 400:
                self._error_count += 1
    
    def get_endpoint_stats(self) -> list[dict]:
        with self._lock:
            stats = []
            for key, count in sorted(self._endpoint_counts.items(), key=lambda x: -x[1]):
                times = self._endpoint_times.get(key, [])
                avg_ms = sum(times) / len(times) if times else 0
                max_ms = max(times) if times else 0
                min_ms = min(times) if times else 0
                stats.append({
                    "endpoint": key,
                    "count": count,
                    "avg_ms": round(avg_ms, 2),
                    "min_ms": round(min_ms, 2),
                    "max_ms": round(max_ms, 2),
                })
            return stats
    
    def get_status_distribution(self) -> dict[str, int]:
        with self._lock:
            return dict(self._status_counts)
    
    def get_summary(self) -> dict[str, Any]:
        with self._lock:
            uptime = time.time() - self._start_time
            rps = self._total_requests / uptime if uptime > 0 else 0
            error_rate = (self._error_count / self._total_requests * 100) if self._total_requests > 0 else 0
            return {
                "total_requests": self._total_requests,
                "error_count": self._error_count,
                "error_rate_percent": round(error_rate, 2),
                "requests_per_second": round(rps, 4),
                "unique_endpoints": len(self._endpoint_counts),
                "uptime_seconds": round(uptime, 1),
            }
    
    def get_top_endpoints(self, limit: int = 10) -> list[dict]:
        stats = self.get_endpoint_stats()
        return stats[:limit]
    
    def get_slowest_endpoints(self, limit: int = 10) -> list[dict]:
        stats = self.get_endpoint_stats()
        return sorted(stats, key=lambda x: -x["avg_ms"])[:limit]
    
    def reset(self):
        with self._lock:
            self._endpoint_counts.clear()
            self._endpoint_times.clear()
            self._status_counts.clear()
            self._error_count = 0
            self._total_requests = 0
            self._start_time = time.time()
