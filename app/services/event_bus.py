import threading
from collections import defaultdict
from datetime import datetime
from typing import Callable, Any


class EventBus:
    def __init__(self):
        self._lock = threading.Lock()
        self._subscribers = defaultdict(list)
        self._event_log = []
        self._max_log = 500
        self._stats = defaultdict(int)
    
    def subscribe(self, event_type: str, handler: Callable):
        with self._lock:
            self._subscribers[event_type].append(handler)
    
    def unsubscribe(self, event_type: str, handler: Callable):
        with self._lock:
            if event_type in self._subscribers:
                self._subscribers[event_type] = [
                    h for h in self._subscribers[event_type] if h != handler
                ]
    
    def publish(self, event_type: str, data: Any = None):
        with self._lock:
            handlers = list(self._subscribers.get(event_type, []))
            self._stats[event_type] += 1
            self._event_log.append({
                "type": event_type,
                "timestamp": datetime.now().isoformat(),
                "handlers_count": len(handlers),
                "data_summary": str(data)[:100] if data else None
            })
            if len(self._event_log) > self._max_log:
                self._event_log = self._event_log[-self._max_log:]
        
        errors = []
        for handler in handlers:
            try:
                handler(event_type, data)
            except Exception as e:
                errors.append({"handler": handler.__name__, "error": str(e)})
        
        return {"event_type": event_type, "handlers_called": len(handlers), "errors": errors}
    
    def get_subscribers(self) -> dict:
        with self._lock:
            return {
                event_type: [h.__name__ for h in handlers]
                for event_type, handlers in self._subscribers.items()
            }
    
    def get_event_log(self, limit: int = 50, event_type: str = None) -> list:
        with self._lock:
            if event_type:
                filtered = [e for e in self._event_log if e["type"] == event_type]
                return list(reversed(filtered[-limit:]))
            return list(reversed(self._event_log[-limit:]))
    
    def get_stats(self) -> dict:
        with self._lock:
            return {
                "total_events": sum(self._stats.values()),
                "event_types": dict(self._stats),
                "subscriber_count": sum(len(h) for h in self._subscribers.values()),
                "registered_events": list(self._subscribers.keys())
            }
    
    def clear_log(self):
        with self._lock:
            self._event_log.clear()
