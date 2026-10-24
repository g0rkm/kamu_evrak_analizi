import hashlib
import json
import os
import threading
from datetime import datetime
from pathlib import Path


class BackupVerifier:
    def __init__(self, backup_dir: str = "data/backups"):
        self._lock = threading.Lock()
        self._backup_dir = Path(backup_dir)
        self._verifications = []
        self._max_history = 50
    
    def verify_backup(self, backup_path: str) -> dict:
        path = Path(backup_path)
        result = {
            "path": str(path),
            "exists": path.exists(),
            "verified_at": datetime.now().isoformat(),
            "valid": False,
            "errors": []
        }
        
        if not path.exists():
            result["errors"].append("Yedek dosyasi bulunamadi")
            self._record(result)
            return result
        
        try:
            stat = path.stat()
            result["size_bytes"] = stat.st_size
            result["modified_at"] = datetime.fromtimestamp(stat.st_mtime).isoformat()
            
            if stat.st_size == 0:
                result["errors"].append("Yedek dosyasi bos")
                self._record(result)
                return result
            
            if path.suffix == ".json":
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                result["record_count"] = len(data) if isinstance(data, list) else 1
                result["checksum"] = self._file_checksum(path)
                result["valid"] = True
            else:
                result["checksum"] = self._file_checksum(path)
                result["valid"] = True
                
        except json.JSONDecodeError as e:
            result["errors"].append(f"JSON parse hatasi: {str(e)}")
        except Exception as e:
            result["errors"].append(f"Dogrulama hatasi: {str(e)}")
        
        self._record(result)
        return result
    
    def list_backups(self) -> list:
        if not self._backup_dir.exists():
            return []
        backups = []
        for f in sorted(self._backup_dir.glob("*"), key=lambda x: x.stat().st_mtime, reverse=True):
            if f.is_file():
                stat = f.stat()
                backups.append({
                    "name": f.name,
                    "path": str(f),
                    "size_bytes": stat.st_size,
                    "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
        return backups
    
    def get_verification_history(self, limit: int = 20) -> list:
        with self._lock:
            return list(reversed(self._verifications[-limit:]))
    
    def _file_checksum(self, path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()
    
    def _record(self, result: dict):
        with self._lock:
            self._verifications.append(result)
            if len(self._verifications) > self._max_history:
                self._verifications = self._verifications[-self._max_history:]
    
    def stats(self) -> dict:
        with self._lock:
            total = len(self._verifications)
            valid = sum(1 for v in self._verifications if v.get("valid"))
            return {
                "total_verifications": total,
                "valid_count": valid,
                "invalid_count": total - valid,
                "backup_dir": str(self._backup_dir),
                "backup_dir_exists": self._backup_dir.exists()
            }
