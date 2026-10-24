import threading
import uuid
from collections import OrderedDict

class CorrelationService:
    def __init__(self, max_entries: int = 1000):
        self._lock = threading.Lock()
        self._correlations = OrderedDict()
        self._max_entries = max_entries
    
    def generate_id(self) -> str:
        return str(uuid.uuid4())
    
    def track(self, correlation_id: str, method: str, path: str, status_code: int = 0, duration_ms: float = 0):
        with self._lock:
            self._correlations[correlation_id] = {
                "id": correlation_id,
                "method": method,
                "path": path,
                "status_code": status_code,
                "duration_ms": round(duration_ms, 2)
            }
            if len(self._correlations) > self._max_entries:
                self._correlations.popitem(last=False)
    
    def get(self, correlation_id: str) -> dict:
        with self._lock:
            return self._correlations.get(correlation_id)
    
    def get_recent(self, limit: int = 50) -> list:
        with self._lock:
            items = list(self._correlations.values())
        return items[-limit:]
    
    def stats(self) -> dict:
        with self._lock:
            return {
                "tracked_requests": len(self._correlations),
                "max_entries": self._max_entries
            }
