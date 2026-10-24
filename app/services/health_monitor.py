import threading
import time
from datetime import datetime
from collections import OrderedDict


class HealthMonitor:
    def __init__(self, check_interval: int = 300):
        self._lock = threading.Lock()
        self._checks = OrderedDict()
        self._history = []
        self._max_history = 100
        self._check_interval = check_interval
        self._last_check = None
        self._status = "healthy"
    
    def register_check(self, name: str, check_fn):
        with self._lock:
            self._checks[name] = {"fn": check_fn, "last_result": None, "last_check": None}
    
    def run_checks(self) -> dict:
        results = {}
        all_healthy = True
        with self._lock:
            for name, check in self._checks.items():
                try:
                    result = check["fn"]()
                    healthy = result if isinstance(result, bool) else bool(result)
                    results[name] = {"healthy": healthy, "detail": str(result) if not isinstance(result, bool) else None}
                    check["last_result"] = healthy
                    check["last_check"] = datetime.now().isoformat()
                    if not healthy:
                        all_healthy = False
                except Exception as e:
                    results[name] = {"healthy": False, "detail": str(e)}
                    check["last_result"] = False
                    check["last_check"] = datetime.now().isoformat()
                    all_healthy = False
            
            self._status = "healthy" if all_healthy else "degraded"
            self._last_check = datetime.now().isoformat()
            
            record = {
                "timestamp": self._last_check,
                "status": self._status,
                "results": dict(results)
            }
            self._history.append(record)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]
        
        return record
    
    def get_status(self) -> dict:
        with self._lock:
            return {
                "status": self._status,
                "last_check": self._last_check,
                "registered_checks": list(self._checks.keys()),
                "check_interval": self._check_interval,
                "checks": {
                    name: {"last_result": c["last_result"], "last_check": c["last_check"]}
                    for name, c in self._checks.items()
                }
            }
    
    def get_history(self, limit: int = 20) -> list:
        with self._lock:
            return list(reversed(self._history[-limit:]))
    
    def is_healthy(self) -> bool:
        with self._lock:
            return self._status == "healthy"
