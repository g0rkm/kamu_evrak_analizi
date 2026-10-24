import json
import csv
import io
import threading
from datetime import datetime
from pathlib import Path

class ExportService:
    def __init__(self, history_dir: str = "data/history"):
        self.history_dir = Path(history_dir)
        self._lock = threading.Lock()
    
    def export_json(self, records: list, pretty: bool = True) -> str:
        if pretty:
            return json.dumps(records, ensure_ascii=False, indent=2, default=str)
        return json.dumps(records, ensure_ascii=False, default=str)
    
    def export_csv(self, records: list) -> str:
        if not records:
            return ""
        output = io.StringIO()
        all_keys = set()
        for r in records:
            if isinstance(r, dict):
                all_keys.update(r.keys())
        fieldnames = sorted(all_keys)
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        for r in records:
            if isinstance(r, dict):
                flat = {}
                for k, v in r.items():
                    if isinstance(v, (dict, list)):
                        flat[k] = json.dumps(v, ensure_ascii=False, default=str)
                    else:
                        flat[k] = v
                writer.writerow(flat)
        return output.getvalue()
    
    def export_summary(self, records: list) -> dict:
        total = len(records)
        if total == 0:
            return {"total": 0, "date_range": None, "categories": {}}
        categories = {}
        dates = []
        for r in records:
            if isinstance(r, dict):
                cat = r.get("category", r.get("siniflandirma", {}).get("kategori", "bilinmiyor"))
                if isinstance(cat, dict):
                    cat = cat.get("kategori", "bilinmiyor")
                categories[cat] = categories.get(cat, 0) + 1
                ts = r.get("timestamp", r.get("created_at", ""))
                if ts:
                    dates.append(str(ts))
        dates.sort()
        return {
            "total": total,
            "date_range": {"start": dates[0], "end": dates[-1]} if dates else None,
            "categories": categories,
            "exported_at": datetime.now().isoformat()
        }
    
    def get_all_records(self) -> list:
        records = []
        if not self.history_dir.exists():
            return records
        for f in sorted(self.history_dir.glob("*.json")):
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                    if isinstance(data, list):
                        records.extend(data)
                    elif isinstance(data, dict):
                        records.append(data)
            except (json.JSONDecodeError, OSError):
                pass
        return records
