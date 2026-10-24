import threading
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from collections import deque

class LogService:
    def __init__(self, log_dir: str = "data/logs", max_memory_logs: int = 500):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._recent_logs = deque(maxlen=max_memory_logs)
    
    def log(self, level: str, message: str, source: str = "system", details: dict = None):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level.upper(),
            "source": source,
            "message": message,
            "details": details or {}
        }
        with self._lock:
            self._recent_logs.append(entry)
            self._write_to_file(entry)
        return entry
    
    def _write_to_file(self, entry: dict):
        date_str = datetime.now().strftime("%Y-%m-%d")
        log_file = self.log_dir / f"{date_str}.jsonl"
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass
    
    def get_recent(self, limit: int = 50, level: str = None, source: str = None) -> list:
        with self._lock:
            logs = list(self._recent_logs)
        if level:
            logs = [l for l in logs if l["level"] == level.upper()]
        if source:
            logs = [l for l in logs if l["source"] == source]
        return logs[-limit:]
    
    def get_log_files(self) -> list:
        files = []
        for f in sorted(self.log_dir.glob("*.jsonl"), reverse=True):
            stat = f.stat()
            files.append({
                "name": f.name,
                "date": f.stem,
                "size_bytes": stat.st_size,
                "size_human": self._human_size(stat.st_size)
            })
        return files
    
    def read_log_file(self, date_str: str, limit: int = 100, offset: int = 0) -> dict:
        log_file = self.log_dir / f"{date_str}.jsonl"
        if not log_file.exists():
            return {"error": "Log dosyasi bulunamadi", "entries": [], "total": 0}
        entries = []
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entries.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
        except Exception:
            pass
        total = len(entries)
        return {"entries": entries[offset:offset+limit], "total": total, "offset": offset, "limit": limit}
    
    def cleanup_old_logs(self, days: int = 30) -> int:
        cutoff = datetime.now() - timedelta(days=days)
        removed = 0
        for f in self.log_dir.glob("*.jsonl"):
            try:
                file_date = datetime.strptime(f.stem, "%Y-%m-%d")
                if file_date < cutoff:
                    f.unlink()
                    removed += 1
            except (ValueError, OSError):
                pass
        return removed
    
    def stats(self) -> dict:
        with self._lock:
            recent_count = len(self._recent_logs)
        files = self.get_log_files()
        total_size = sum(f["size_bytes"] for f in files)
        return {
            "recent_in_memory": recent_count,
            "log_files": len(files),
            "total_size_bytes": total_size,
            "total_size_human": self._human_size(total_size)
        }
    
    @staticmethod
    def _human_size(size_bytes: int) -> str:
        for unit in ("B", "KB", "MB", "GB"):
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"
