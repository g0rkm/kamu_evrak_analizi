import csv
import io
import json
from typing import List


class ExportService:
    """Kayitlari CSV ve JSON formatinda disariya aktarma servisi."""

    EXPORT_FIELDS = [
        "id", "created_at", "source_name", "document_type", "summary",
        "priority", "favorite", "archived", "tags", "notes",
    ]

    @staticmethod
    def to_csv(records: List[dict]) -> str:
        """Kayitlari CSV formatinda dondurur."""
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=ExportService.EXPORT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            row = {}
            for field in ExportService.EXPORT_FIELDS:
                val = record.get(field, "")
                if isinstance(val, list):
                    val = ", ".join(str(v) for v in val)
                elif isinstance(val, bool):
                    val = "Evet" if val else "Hayir"
                row[field] = val
            writer.writerow(row)
        return output.getvalue()

    @staticmethod
    def to_json(records: List[dict], pretty: bool = True) -> str:
        """Kayitlari JSON formatinda dondurur."""
        export_data = []
        for record in records:
            item = {field: record.get(field, "") for field in ExportService.EXPORT_FIELDS}
            export_data.append(item)
        if pretty:
            return json.dumps(export_data, indent=2, ensure_ascii=False, default=str)
        return json.dumps(export_data, ensure_ascii=False, default=str)

    @staticmethod
    def summary_report(records: List[dict]) -> dict:
        """Kayitlarin ozet raporunu olusturur."""
        total = len(records)
        by_type = {}
        by_priority = {}
        tags_count = {}
        for r in records:
            dt = r.get("document_type", "bilinmiyor")
            by_type[dt] = by_type.get(dt, 0) + 1
            pr = r.get("priority", "normal")
            by_priority[pr] = by_priority.get(pr, 0) + 1
            for tag in r.get("tags", []):
                tags_count[tag] = tags_count.get(tag, 0) + 1
        top_tags = sorted(tags_count.items(), key=lambda x: x[1], reverse=True)[:10]
        return {
            "total_records": total,
            "by_document_type": by_type,
            "by_priority": by_priority,
            "top_tags": [{"tag": t, "count": c} for t, c in top_tags],
            "archived_count": sum(1 for r in records if r.get("archived")),
            "favorite_count": sum(1 for r in records if r.get("favorite")),
        }
