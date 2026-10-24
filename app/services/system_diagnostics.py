import os
import sys
import platform
import threading
import time
from datetime import datetime
from pathlib import Path


class SystemDiagnostics:
    def __init__(self):
        self._lock = threading.Lock()
        self._start_time = time.time()
    
    def get_system_info(self) -> dict:
        return {
            "python_version": sys.version,
            "platform": platform.platform(),
            "architecture": platform.architecture()[0],
            "processor": platform.processor() or "unknown",
            "hostname": platform.node(),
            "os_name": os.name,
            "pid": os.getpid(),
            "thread_count": threading.active_count(),
            "uptime_seconds": round(time.time() - self._start_time, 1)
        }
    
    def get_memory_info(self) -> dict:
        try:
            import resource
            usage = resource.getrusage(resource.RUSAGE_SELF)
            return {
                "max_rss_kb": usage.ru_maxrss,
                "available": True
            }
        except ImportError:
            return {
                "available": False,
                "note": "resource module not available on Windows"
            }
    
    def get_disk_usage(self, path: str = ".") -> dict:
        try:
            import shutil
            usage = shutil.disk_usage(path)
            return {
                "total_gb": round(usage.total / (1024**3), 2),
                "used_gb": round(usage.used / (1024**3), 2),
                "free_gb": round(usage.free / (1024**3), 2),
                "usage_percent": round(usage.used / usage.total * 100, 1)
            }
        except Exception as e:
            return {"error": str(e)}
    
    def get_data_dir_stats(self, data_dir: str) -> dict:
        path = Path(data_dir)
        if not path.exists():
            return {"exists": False, "path": str(path)}
        
        total_files = 0
        total_size = 0
        dir_counts = {}
        
        for item in path.rglob("*"):
            if item.is_file():
                total_files += 1
                total_size += item.stat().st_size
                parent = str(item.parent.relative_to(path))
                dir_counts[parent] = dir_counts.get(parent, 0) + 1
        
        return {
            "exists": True,
            "path": str(path),
            "total_files": total_files,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "subdirectories": dict(sorted(dir_counts.items()))
        }
    
    def get_full_diagnostics(self, data_dir: str = "data") -> dict:
        return {
            "timestamp": datetime.now().isoformat(),
            "system": self.get_system_info(),
            "memory": self.get_memory_info(),
            "disk": self.get_disk_usage(),
            "data_directory": self.get_data_dir_stats(data_dir)
        }
