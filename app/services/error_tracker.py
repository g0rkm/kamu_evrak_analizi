import threading
from datetime import datetime
from collections import deque

class ErrorTracker:
    def __init__(self, max_errors: int = 200):
        self._lock = threading.Lock()
        self._errors = deque(maxlen=max_errors)
        self._counts = {}
        self._total = 0
    
    def track(self, error_type: str, message: str, path: str = "", details: dict = None):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": error_type,
            "message": str(message)[:500],
            "path": path,
            "details": details or {}
        }
        with self._lock:
            self._errors.append(entry)
            self._counts[error_type] = self._counts.get(error_type, 0) + 1
            self._total += 1
        return entry
    
    def get_recent(self, limit: int = 50, error_type: str = None) -> list:
        with self._lock:
            errors = list(self._errors)
        if error_type:
            errors = [e for e in errors if e["type"] == error_type]
        return errors[-limit:]
    
    def get_summary(self) -> dict:
        with self._lock:
            return {
                "total_errors": self._total,
                "error_types": dict(self._counts),
                "recent_count": len(self._errors),
                "last_error": self._errors[-1] if self._errors else None
            }
    
    def get_top_errors(self, limit: int = 10) -> list:
        with self._lock:
            sorted_errors = sorted(self._counts.items(), key=lambda x: x[1], reverse=True)
        return [{"type": t, "count": c} for t, c in sorted_errors[:limit]]
    
    def clear(self):
        with self._lock:
            self._errors.clear()
            self._counts.clear()
            self._total = 0
