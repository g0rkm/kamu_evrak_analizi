import json
import threading
import time
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

class AuditLogger:
    SUPPORTED_ACTIONS = {
        "analyze", "delete", "update_tags", "update_notes", 
        "archive", "unarchive", "favorite", "bulk_delete", 
        "export", "import_records", "login"
    }

    def __init__(self, log_dir: str):
        self._log_dir = Path(log_dir)
        self._lock = threading.Lock()
        self._log_file = self._log_dir / "audit.jsonl"
        
        # Dizin yoksa oluştur
        self._log_dir.mkdir(parents=True, exist_ok=True)

    def log(self, action: str, details: Optional[Dict[str, Any]] = None, user: str = "system", record_id: Optional[str] = None) -> None:
        if action not in self.SUPPORTED_ACTIONS:
            # İsteğe bağlı olarak bilinmeyen action'lar için uyarı verilebilir veya kabul edilebilir.
            pass

        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "action": action,
            "user": user,
            "record_id": record_id,
            "details": details or {}
        }

        with self._lock:
            with open(self._log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def get_logs(self, limit: int = 100, action: Optional[str] = None, record_id: Optional[str] = None) -> List[Dict[str, Any]]:
        logs = []
        with self._lock:
            if not self._log_file.exists():
                return logs

            with open(self._log_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        # Filtreleme
                        if action and entry.get("action") != action:
                            continue
                        if record_id and entry.get("record_id") != record_id:
                            continue
                        logs.append(entry)
                    except json.JSONDecodeError:
                        continue

        # Son N kaydı dönmek için sondan kesiyoruz (veya kronolojik olarak son eklenenler)
        return logs[-limit:]

    def clear_old_logs(self, days: int = 90) -> int:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        retained_logs = []
        removed_count = 0

        with self._lock:
            if not self._log_file.exists():
                return 0

            with open(self._log_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        ts_str = entry.get("timestamp", "").rstrip("Z")
                        entry_date = datetime.fromisoformat(ts_str)
                        if entry_date >= cutoff_date:
                            retained_logs.append(line)
                        else:
                            removed_count += 1
                    except (ValueError, json.JSONDecodeError):
                        # Bozuk satırları kaybetmemek adına tutabiliriz ya da atlayabiliriz
                        retained_logs.append(line)

            with open(self._log_file, "w", encoding="utf-8") as f:
                for line in retained_logs:
                    f.write(line + "\n")

        return removed_count

    def stats(self) -> Dict[str, Any]:
        total_logs = 0
        action_counts: Dict[str, int] = {}
        last_log_date: Optional[str] = None

        with self._lock:
            if not self._log_file.exists():
                return {
                    "total_logs": 0,
                    "action_counts": {},
                    "last_log_date": None
                }

            with open(self._log_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        total_logs += 1
                        act = entry.get("action", "unknown")
                        action_counts[act] = action_counts.get(act, 0) + 1
                        last_log_date = entry.get("timestamp")
                    except json.JSONDecodeError:
                        continue

        return {
            "total_logs": total_logs,
            "action_counts": action_counts,
            "last_log_date": last_log_date
        }
