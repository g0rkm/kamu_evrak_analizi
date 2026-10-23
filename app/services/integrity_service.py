import hashlib
import os
from typing import Optional


class IntegrityService:
    """Dosya butunluk kontrolu servisi - SHA-256 hash hesaplama ve dogrulama."""

    @staticmethod
    def compute_hash(file_path: str) -> Optional[str]:
        """Dosyanin SHA-256 hash'ini hesaplar."""
        if not os.path.exists(file_path):
            return None
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    @staticmethod
    def compute_hash_from_bytes(data: bytes) -> str:
        """Byte verisinin SHA-256 hash'ini hesaplar."""
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def verify_hash(file_path: str, expected_hash: str) -> bool:
        """Dosyanin hash'ini dogrular."""
        actual = IntegrityService.compute_hash(file_path)
        if actual is None:
            return False
        return actual == expected_hash

    @staticmethod
    def compute_checksum(data: dict) -> str:
        """Kayit verisinin checksum'ini hesaplar (JSON stabilize edilmis)."""
        import json
        stable = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(stable.encode("utf-8")).hexdigest()

    @staticmethod
    def verify_record_integrity(record: dict) -> dict:
        """Kaydin butunlugunu kontrol eder."""
        result = {"valid": True, "issues": []}
        required_fields = ["id", "created_at"]
        for field in required_fields:
            if field not in record:
                result["valid"] = False
                result["issues"].append(f"Eksik alan: {field}")
        if "file_hash" in record and "file_path" in record:
            if os.path.exists(record["file_path"]):
                actual = IntegrityService.compute_hash(record["file_path"])
                if actual != record["file_hash"]:
                    result["valid"] = False
                    result["issues"].append("Dosya hash uyusmazligi")
            else:
                result["issues"].append("Dosya bulunamadi")
        return result
