import threading
from datetime import datetime

class MaintenanceService:
    def __init__(self, initial_mode: bool = False):
        self._lock = threading.Lock()
        self._maintenance = initial_mode
        self._reason = ""
        self._started_at = None
        self._history = []
    
    @property
    def is_active(self) -> bool:
        with self._lock:
            return self._maintenance
    
    def enable(self, reason: str = "") -> dict:
        with self._lock:
            self._maintenance = True
            self._reason = reason
            self._started_at = datetime.now().isoformat()
            self._history.append({"action": "enable", "reason": reason, "at": self._started_at})
        return self.status()
    
    def disable(self) -> dict:
        with self._lock:
            was_active = self._maintenance
            self._maintenance = False
            ended_at = datetime.now().isoformat()
            if was_active:
                self._history.append({"action": "disable", "at": ended_at, "was_started_at": self._started_at})
            self._reason = ""
            self._started_at = None
        return self.status()
    
    def status(self) -> dict:
        with self._lock:
            return {
                "maintenance_mode": self._maintenance,
                "reason": self._reason,
                "started_at": self._started_at,
                "history_count": len(self._history)
            }
    
    def get_history(self, limit: int = 20) -> list:
        with self._lock:
            return list(reversed(self._history[-limit:]))
