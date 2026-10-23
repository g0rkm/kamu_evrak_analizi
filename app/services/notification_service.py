import json
import os
import threading
import datetime
from typing import Optional


class NotificationService:
    """Dahili bildirim sistemi - onemli olaylari kaydeder ve sorgular."""

    def __init__(self, storage_dir: str):
        self._dir = storage_dir
        os.makedirs(self._dir, exist_ok=True)
        self._file = os.path.join(self._dir, "notifications.jsonl")
        self._lock = threading.Lock()

    def send(self, level: str, title: str, message: str, source: str = "system", metadata: dict = None):
        """Bildirim olusturur ve kaydeder."""
        valid_levels = ["info", "warning", "error", "critical"]
        if level not in valid_levels:
            level = "info"
        entry = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "level": level,
            "title": title,
            "message": message,
            "source": source,
            "read": False,
            "metadata": metadata or {},
        }
        with self._lock:
            with open(self._file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
        return entry

    def get_notifications(self, limit: int = 50, level: str = None, unread_only: bool = False) -> list:
        """Bildirimleri sorgular."""
        if not os.path.exists(self._file):
            return []
        with self._lock:
            with open(self._file, "r", encoding="utf-8") as f:
                lines = f.readlines()
        notifications = []
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if level and entry.get("level") != level:
                continue
            if unread_only and entry.get("read"):
                continue
            notifications.append(entry)
            if len(notifications) >= limit:
                break
        return notifications

    def unread_count(self) -> int:
        """Okunmamis bildirim sayisini dondurur."""
        notifications = self.get_notifications(limit=10000, unread_only=True)
        return len(notifications)

    def mark_all_read(self):
        """Tum bildirimleri okundu olarak isaretler."""
        if not os.path.exists(self._file):
            return 0
        with self._lock:
            with open(self._file, "r", encoding="utf-8") as f:
                lines = f.readlines()
            count = 0
            updated = []
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if not entry.get("read"):
                        entry["read"] = True
                        count += 1
                    updated.append(json.dumps(entry, ensure_ascii=False, default=str))
                except json.JSONDecodeError:
                    updated.append(line)
            with open(self._file, "w", encoding="utf-8") as f:
                f.write("\n".join(updated) + "\n")
        return count

    def stats(self) -> dict:
        """Bildirim istatistiklerini dondurur."""
        notifications = self.get_notifications(limit=10000)
        by_level = {}
        for n in notifications:
            lvl = n.get("level", "info")
            by_level[lvl] = by_level.get(lvl, 0) + 1
        return {
            "total": len(notifications),
            "unread": sum(1 for n in notifications if not n.get("read")),
            "by_level": by_level,
        }
