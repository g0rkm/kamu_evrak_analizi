import logging
import threading
import time
from datetime import datetime, timezone
from typing import Callable, Optional

logger = logging.getLogger("scheduler")


class ScheduledTask:
    """Zamanlanmis gorev tanimi."""

    def __init__(self, name: str, func: Callable, interval_seconds: int, enabled: bool = True):
        self.name = name
        self.func = func
        self.interval = interval_seconds
        self.enabled = enabled
        self.last_run = None
        self.next_run = None
        self.run_count = 0
        self.last_error = None


class SchedulerService:
    """Basit zamanlayici servisi - periyodik gorevleri calistirir."""

    def __init__(self):
        self._tasks = {}
        self._running = False
        self._thread = None
        self._lock = threading.Lock()

    def add_task(self, name: str, func: Callable, interval_seconds: int, enabled: bool = True):
        """Yeni zamanlanmis gorev ekler."""
        task = ScheduledTask(name, func, interval_seconds, enabled)
        task.next_run = time.time() + interval_seconds
        with self._lock:
            self._tasks[name] = task
        logger.info(f"Gorev eklendi: {name} (her {interval_seconds}s)")

    def remove_task(self, name: str) -> bool:
        """Gorevi kaldirir."""
        with self._lock:
            if name in self._tasks:
                del self._tasks[name]
                return True
        return False

    def start(self):
        """Zamanlayiciyi baslatir."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("Zamanlayici baslatildi")

    def stop(self):
        """Zamanlayiciyi durdurur."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Zamanlayici durduruldu")

    def _run_loop(self):
        """Ana zamanlayici dongusu."""
        while self._running:
            now = time.time()
            with self._lock:
                tasks = list(self._tasks.values())
            for task in tasks:
                if not task.enabled:
                    continue
                if task.next_run and now >= task.next_run:
                    try:
                        task.func()
                        task.last_run = datetime.now(timezone.utc).isoformat()
                        task.run_count += 1
                        task.last_error = None
                        logger.debug(f"Gorev tamamlandi: {task.name}")
                    except Exception as e:
                        task.last_error = str(e)
                        logger.error(f"Gorev hatasi: {task.name}: {e}")
                    task.next_run = now + task.interval
            time.sleep(1)

    def list_tasks(self) -> list:
        """Tum gorevleri listeler."""
        with self._lock:
            return [
                {
                    "name": t.name,
                    "interval_seconds": t.interval,
                    "enabled": t.enabled,
                    "last_run": t.last_run,
                    "run_count": t.run_count,
                    "last_error": t.last_error,
                }
                for t in self._tasks.values()
            ]

    def task_stats(self) -> dict:
        """Gorev istatistiklerini dondurur."""
        with self._lock:
            tasks = list(self._tasks.values())
        return {
            "total_tasks": len(tasks),
            "active_tasks": sum(1 for t in tasks if t.enabled),
            "total_runs": sum(t.run_count for t in tasks),
            "errors": sum(1 for t in tasks if t.last_error),
        }
