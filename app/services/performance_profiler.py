import threading
import time
from collections import defaultdict
from datetime import datetime


class PerformanceProfiler:
    def __init__(self, slow_threshold_ms: float = 1000):
        self._lock = threading.Lock()
        self._slow_threshold = slow_threshold_ms
        self._endpoint_times = defaultdict(list)
        self._slow_requests = []
        self._max_slow = 100
        self._max_samples = 1000
    
    def record(self, method: str, path: str, duration_ms: float, status_code: int = 200):
        key = f"{method} {path}"
        with self._lock:
            samples = self._endpoint_times[key]
            samples.append(duration_ms)
            if len(samples) > self._max_samples:
                self._endpoint_times[key] = samples[-self._max_samples:]
            
            if duration_ms >= self._slow_threshold:
                self._slow_requests.append({
                    "method": method,
                    "path": path,
                    "duration_ms": round(duration_ms, 2),
                    "status_code": status_code,
                    "timestamp": datetime.now().isoformat()
                })
                if len(self._slow_requests) > self._max_slow:
                    self._slow_requests = self._slow_requests[-self._max_slow:]
    
    def get_slow_requests(self, limit: int = 20) -> list:
        with self._lock:
            return list(reversed(self._slow_requests[-limit:]))
    
    def get_endpoint_profile(self, endpoint: str = None) -> dict:
        with self._lock:
            if endpoint and endpoint in self._endpoint_times:
                samples = self._endpoint_times[endpoint]
                return self._calc_stats(endpoint, samples)
            
            result = {}
            for key, samples in self._endpoint_times.items():
                result[key] = self._calc_stats(key, samples)
            return result
    
    def _calc_stats(self, key: str, samples: list) -> dict:
        if not samples:
            return {"count": 0, "avg_ms": 0, "min_ms": 0, "max_ms": 0, "p95_ms": 0}
        sorted_s = sorted(samples)
        p95_idx = int(len(sorted_s) * 0.95)
        return {
            "count": len(samples),
            "avg_ms": round(sum(samples) / len(samples), 2),
            "min_ms": round(sorted_s[0], 2),
            "max_ms": round(sorted_s[-1], 2),
            "p95_ms": round(sorted_s[min(p95_idx, len(sorted_s) - 1)], 2)
        }
    
    def get_summary(self) -> dict:
        with self._lock:
            total_requests = sum(len(v) for v in self._endpoint_times.values())
            all_times = []
            for samples in self._endpoint_times.values():
                all_times.extend(samples)
            return {
                "total_profiled": total_requests,
                "unique_endpoints": len(self._endpoint_times),
                "slow_requests_count": len(self._slow_requests),
                "slow_threshold_ms": self._slow_threshold,
                "global_avg_ms": round(sum(all_times) / len(all_times), 2) if all_times else 0
            }
    
    def reset(self):
        with self._lock:
            self._endpoint_times.clear()
            self._slow_requests.clear()
