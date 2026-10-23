import os
import platform
import shutil
import sys
from datetime import datetime
from typing import Any

try:
    import psutil
except ImportError:
    psutil = None


class HealthChecker:
    """Sistem sağlığını, disk, bellek, python ortamını, servisleri ve veri dizinlerini kontrol eder."""

    def check_disk(self, path: str = ".") -> dict[str, Any]:
        """Belirtilen yoldaki disk kullanımını ve durumunu kontrol eder."""
        usage = shutil.disk_usage(path)
        total_mb = usage.total // (1024 * 1024)
        free_mb = usage.free // (1024 * 1024)
        used_percent = (usage.used / usage.total) * 100 if usage.total > 0 else 0.0
        warning = free_mb < 500

        return {
            "free_mb": free_mb,
            "total_mb": total_mb,
            "used_percent": round(used_percent, 2),
            "warning": warning,
        }

    def check_memory(self) -> dict[str, Any]:
        """Sistem bellek kullanımını kontrol eder (psutil gerektirir)."""
        if psutil is None:
            return {"available": False, "reason": "psutil not installed"}

        mem = psutil.virtual_memory()
        total_mb = mem.total // (1024 * 1024)
        available_mb = mem.available // (1024 * 1024)
        used_percent = mem.percent
        warning = used_percent > 90.0

        return {
            "available": True,
            "total_mb": total_mb,
            "available_mb": available_mb,
            "used_percent": round(used_percent, 2),
            "warning": warning,
        }

    def check_python(self) -> dict[str, str]:
        """Python sürüm ve platform bilgilerini döndürür."""
        return {
            "version": sys.version,
            "platform": platform.platform(),
            "architecture": platform.architecture()[0],
        }

    def check_service(self, name: str, service_obj: Any) -> dict[str, Any]:
        """Verilen servis nesnesinin durumunu ve tipini kontrol eder."""
        is_available = service_obj is not None
        service_type = type(service_obj).__name__ if service_obj else None
        return {
            "name": name,
            "available": is_available,
            "type": service_type,
        }

    def check_data_directories(self) -> dict[str, dict[str, Any]]:
        """Belirli veri dizinlerinin varlığını, yazılabilirliğini ve dosya sayısını kontrol eder."""
        dirs = [
            "data/history",
            "data/audit",
            "data/backups",
            "data/notifications",
            "data/templates",
            "data/auth",
        ]
        results = {}

        for dir_path in dirs:
            exists = os.path.isdir(dir_path)
            writable = os.access(dir_path, os.W_OK) if exists else False
            file_count = 0
            if exists:
                try:
                    file_count = len(os.listdir(dir_path))
                except OSError:
                    file_count = 0

            results[dir_path] = {
                "exists": exists,
                "writable": writable,
                "file_count": file_count,
            }

        return results

    def check_all(self, services: dict[str, Any] = None) -> dict[str, Any]:
        """Tüm sağlık kontrollerini çalıştırır ve genel durumu belirler."""
        if services is None:
            services = {}

        disk_info = self.check_disk()
        memory_info = self.check_memory()
        python_info = self.check_python()
        service_results = {name: self.check_service(name, obj) for name, obj in services.items()}
        dir_results = self.check_data_directories()

        # Durum belirleme mantığı
        # Disk free < 100MB ise -> "unhealthy"
        # Disk warning (free < 500MB) veya memory warning (used > 90%) ise -> "degraded"
        # Aksi halde -> "healthy"
        status = "healthy"

        has_disk_warning = disk_info.get("warning", False)
        has_memory_warning = memory_info.get("available", False) and memory_info.get("warning", False)

        if disk_info.get("free_mb", 0) < 100:
            status = "unhealthy"
        elif has_disk_warning or has_memory_warning:
            status = "degraded"

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "status": status,
            "disk": disk_info,
            "memory": memory_info,
            "python": python_info,
            "services": service_results,
            "directories": dir_results,
        }
