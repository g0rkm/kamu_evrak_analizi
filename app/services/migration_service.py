import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("migration")

SCHEMA_VERSION = 2

REQUIRED_FIELDS_V2 = {
    "id": str,
    "created_at": str,
}

OPTIONAL_FIELDS_V2 = {
    "source_name": str,
    "document_type": str,
    "summary": str,
    "priority": str,
    "favorite": bool,
    "archived": bool,
    "deleted": bool,
    "tags": list,
    "notes": str,
    "file_hash": str,
    "changelog": list,
}


class MigrationService:
    """Kayit sema migrasyonu ve veri dogrulama servisi."""

    def __init__(self, history_dir: str):
        self._dir = history_dir
        self._meta_file = os.path.join(history_dir, "_migration_meta.json")

    def get_current_version(self) -> int:
        """Mevcut sema versiyonunu dondurur."""
        if os.path.exists(self._meta_file):
            with open(self._meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)
                return meta.get("schema_version", 1)
        return 1

    def _set_version(self, version: int):
        meta = {"schema_version": version, "updated_at": datetime.now(timezone.utc).isoformat()}
        with open(self._meta_file, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

    def migrate_record(self, record: dict) -> dict:
        """Kaydi en son sema versiyonuna gunceller."""
        version = record.get("_schema_version", 1)
        if version < 2:
            record = self._migrate_v1_to_v2(record)
        record["_schema_version"] = SCHEMA_VERSION
        return record

    def _migrate_v1_to_v2(self, record: dict) -> dict:
        """V1 -> V2 migrasyonu: eksik alanlari varsayilan degerlerle doldur."""
        defaults = {
            "priority": "normal",
            "favorite": False,
            "archived": False,
            "deleted": False,
            "tags": [],
            "notes": "",
            "changelog": [],
        }
        for key, default in defaults.items():
            if key not in record:
                record[key] = default
        if "created_at" not in record:
            record["created_at"] = datetime.now(timezone.utc).isoformat()
        return record

    def validate_record(self, record: dict) -> dict:
        """Kaydi dogrular, sorunlari raporlar."""
        issues = []
        for field, ftype in REQUIRED_FIELDS_V2.items():
            if field not in record:
                issues.append(f"Eksik zorunlu alan: {field}")
            elif not isinstance(record[field], ftype):
                issues.append(f"Yanlis tip: {field} ({type(record[field]).__name__} != {ftype.__name__})")
        for field, ftype in OPTIONAL_FIELDS_V2.items():
            if field in record and not isinstance(record[field], ftype):
                issues.append(f"Yanlis tip: {field} ({type(record[field]).__name__} != {ftype.__name__})")
        return {"valid": len(issues) == 0, "issues": issues, "schema_version": record.get("_schema_version", 1)}

    def migrate_all(self, records: list) -> dict:
        """Tum kayitlari migrate eder."""
        migrated = 0
        errors = 0
        for record in records:
            try:
                version = record.get("_schema_version", 1)
                if version < SCHEMA_VERSION:
                    self.migrate_record(record)
                    migrated += 1
            except Exception as e:
                errors += 1
                logger.error(f"Migrasyon hatasi: {record.get('id', '?')}: {e}")
        self._set_version(SCHEMA_VERSION)
        return {"migrated": migrated, "errors": errors, "target_version": SCHEMA_VERSION}

    def schema_report(self, records: list) -> dict:
        """Kayitlarin sema durumu raporu."""
        version_counts = {}
        valid_count = 0
        invalid_count = 0
        for r in records:
            v = r.get("_schema_version", 1)
            version_counts[v] = version_counts.get(v, 0) + 1
            result = self.validate_record(r)
            if result["valid"]:
                valid_count += 1
            else:
                invalid_count += 1
        return {
            "current_schema_version": SCHEMA_VERSION,
            "version_distribution": version_counts,
            "valid_records": valid_count,
            "invalid_records": invalid_count,
            "total_records": len(records),
        }
