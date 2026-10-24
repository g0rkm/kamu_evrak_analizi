import threading
import time
from collections import deque
from datetime import datetime
from typing import Callable, Optional


class WebhookRetry:
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 60.0):
        self._lock = threading.Lock()
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._max_delay = max_delay
        self._pending = deque(maxlen=500)
        self._history = deque(maxlen=200)
        self._stats = {"total_sent": 0, "total_failed": 0, "total_retried": 0}
    
    def send_with_retry(self, url: str, payload: dict, send_fn: Callable) -> dict:
        attempt = 0
        last_error = None
        
        while attempt <= self._max_retries:
            try:
                result = send_fn(url, payload)
                with self._lock:
                    self._stats["total_sent"] += 1
                    if attempt > 0:
                        self._stats["total_retried"] += 1
                    self._history.append({
                        "url": url,
                        "status": "success",
                        "attempts": attempt + 1,
                        "timestamp": datetime.now().isoformat()
                    })
                return {"success": True, "attempts": attempt + 1, "result": result}
            except Exception as e:
                last_error = str(e)
                attempt += 1
                if attempt <= self._max_retries:
                    delay = min(self._base_delay * (2 ** (attempt - 1)), self._max_delay)
                    time.sleep(delay)
        
        with self._lock:
            self._stats["total_failed"] += 1
            self._history.append({
                "url": url,
                "status": "failed",
                "attempts": attempt,
                "error": last_error,
                "timestamp": datetime.now().isoformat()
            })
        return {"success": False, "attempts": attempt, "error": last_error}
    
    def queue_webhook(self, url: str, payload: dict):
        with self._lock:
            self._pending.append({
                "url": url,
                "payload": payload,
                "queued_at": datetime.now().isoformat()
            })
    
    def get_pending(self) -> list:
        with self._lock:
            return list(self._pending)
    
    def get_history(self, limit: int = 50) -> list:
        with self._lock:
            return list(reversed(list(self._history)[-limit:]))
    
    def get_stats(self) -> dict:
        with self._lock:
            return {
                **self._stats,
                "pending_count": len(self._pending),
                "max_retries": self._max_retries,
                "base_delay": self._base_delay
            }
    
    def clear_pending(self) -> int:
        with self._lock:
            count = len(self._pending)
            self._pending.clear()
            return count
