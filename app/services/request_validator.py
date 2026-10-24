import re
from typing import Any, Optional


class RequestValidator:
    MAX_TEXT_LENGTH = 100000
    MAX_FILENAME_LENGTH = 255
    MIN_TEXT_LENGTH = 1
    
    ALLOWED_SORT_FIELDS = {"created_at", "updated_at", "title", "status", "document_type"}
    ALLOWED_SORT_ORDERS = {"asc", "desc"}
    
    @staticmethod
    def validate_text(text: Any, field_name: str = "text", max_length: int = None) -> dict:
        max_len = max_length or RequestValidator.MAX_TEXT_LENGTH
        errors = []
        if text is None:
            errors.append(f"{field_name} alani zorunludur")
        elif not isinstance(text, str):
            errors.append(f"{field_name} metin olmalidir")
        elif len(text.strip()) < RequestValidator.MIN_TEXT_LENGTH:
            errors.append(f"{field_name} bos olamaz")
        elif len(text) > max_len:
            errors.append(f"{field_name} en fazla {max_len} karakter olabilir")
        return {"valid": len(errors) == 0, "errors": errors}
    
    @staticmethod
    def validate_pagination(offset: Any = 0, limit: Any = 20) -> dict:
        errors = []
        try:
            offset = int(offset)
            limit = int(limit)
        except (ValueError, TypeError):
            return {"valid": False, "errors": ["offset and limit sayisal olmalidir"], "offset": 0, "limit": 20}
        if offset < 0:
            errors.append("offset negatif olamaz")
        if limit < 1:
            errors.append("limit en az 1 olmalidir")
        if limit > 500:
            errors.append("limit en fazla 500 olabilir")
        return {"valid": len(errors) == 0, "errors": errors, "offset": max(0, offset), "limit": min(max(1, limit), 500)}
    
    @staticmethod
    def validate_sort(sort_by: Optional[str] = None, order: Optional[str] = None) -> dict:
        errors = []
        if sort_by and sort_by not in RequestValidator.ALLOWED_SORT_FIELDS:
            errors.append(f"Gecersiz siralama alani: {sort_by}. Izin verilenler: {', '.join(sorted(RequestValidator.ALLOWED_SORT_FIELDS))}")
        if order and order.lower() not in RequestValidator.ALLOWED_SORT_ORDERS:
            errors.append(f"Gecersiz siralama yonu: {order}. Izin verilenler: asc, desc")
        return {"valid": len(errors) == 0, "errors": errors}
    
    @staticmethod
    def validate_id(record_id: Any, field_name: str = "id") -> dict:
        errors = []
        if not record_id:
            errors.append(f"{field_name} zorunludur")
        elif not isinstance(record_id, str):
            errors.append(f"{field_name} metin olmalidir")
        elif len(record_id) > 100:
            errors.append(f"{field_name} cok uzun")
        elif not re.match(r'^[\w\-]+$', record_id):
            errors.append(f"{field_name} gecersiz karakterler iceriyor")
        return {"valid": len(errors) == 0, "errors": errors}
    
    @staticmethod
    def validate_ids(ids: Any, field_name: str = "ids", max_count: int = 100) -> dict:
        errors = []
        if not isinstance(ids, list):
            return {"valid": False, "errors": [f"{field_name} liste olmalidir"]}
        if len(ids) == 0:
            errors.append(f"{field_name} bos olamaz")
        if len(ids) > max_count:
            errors.append(f"{field_name} en fazla {max_count} eleman icermeli")
        for i, item in enumerate(ids[:5]):
            v = RequestValidator.validate_id(item, f"{field_name}[{i}]")
            errors.extend(v["errors"])
        return {"valid": len(errors) == 0, "errors": errors}
    
    @staticmethod
    def validate_date_range(start_date: Optional[str] = None, end_date: Optional[str] = None) -> dict:
        from datetime import datetime
        errors = []
        parsed_start = None
        parsed_end = None
        for label, val in [("start_date", start_date), ("end_date", end_date)]:
            if val:
                try:
                    parsed = datetime.fromisoformat(val.replace("Z", "+00:00"))
                    if label == "start_date":
                        parsed_start = parsed
                    else:
                        parsed_end = parsed
                except ValueError:
                    errors.append(f"{label} gecerli ISO tarih formati olmalidir")
        if parsed_start and parsed_end and parsed_start > parsed_end:
            errors.append("start_date, end_date'den sonra olamaz")
        return {"valid": len(errors) == 0, "errors": errors}
