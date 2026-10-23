import os
import unicodedata
from pathlib import Path
from typing import Any

class FileValidator:
    ALLOWED_EXTENSIONS = {
        '.pdf', '.docx', '.doc', '.txt', '.xlsx', '.xls', '.csv', 
        '.png', '.jpg', '.jpeg', '.tiff', '.bmp'
    }
    
    ALLOWED_MIME_TYPES = {
        'application/pdf',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/msword',
        'text/plain',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/vnd.ms-excel',
        'text/csv',
        'image/png',
        'image/jpeg',
        'image/tiff',
        'image/bmp'
    }

    def __init__(self, max_file_size_mb: int = 50) -> None:
        self.max_file_size_mb = max_file_size_mb

    def validate_extension(self, filename: str) -> bool:
        if not filename:
            return False
        ext = Path(filename).suffix.lower()
        return ext in self.ALLOWED_EXTENSIONS

    def validate_size(self, file_size_bytes: int) -> bool:
        if file_size_bytes is None or file_size_bytes < 0:
            return False
        max_size_bytes = self.max_file_size_mb * 1024 * 1024
        return file_size_bytes <= max_size_bytes

    def validate_filename(self, filename: str) -> str:
        if not filename:
            return "unnamed_file"
        
        # Path sanitization: sadece dosya adını al (klasor yollarini ayikla)
        base_name = os.path.basename(filename)
        
        # Unicode normalization (NFKC)
        normalized = unicodedata.normalize('NFKC', base_name)
        
        # Tehlikeli karakterleri veya bosluklari temizleme (guvenli karakterler birakilabilir)
        # Guvenli bir dosyaadi olusturmak icin path guvenligi saglanir
        clean_name = "".(c for c in normalized if c.isalnum() or c in (' ', '.', '_', '-')).strip()
        if not clean_name:
            clean_name = "unnamed_file"
            
        # Max 255 karakter siniri (uzantiyi korumaya calisarak)
        if len(clean_name) > 255:
            p = Path(clean_name)
            stem = p.stem
            suffix = p.suffix
            max_stem_len = 255 - len(suffix)
            if max_stem_len > 0:
                clean_name = stem[:max_stem_len] + suffix
            else:
                clean_name = clean_name[:255]
                
        return clean_name

    def get_file_type_label(self, filename: str) -> str:
        if not filename:
            return "Bilinmeyen"
            
        ext = Path(filename).suffix.lower()
        if ext == '.pdf':
            return "PDF Belgesi"
        elif ext in {'.docx', '.doc'}:
            return "Word Belgesi"
        elif ext == '.txt':
            return "Metin Dosyası"
        elif ext in {'.xlsx', '.xls', '.csv'}:
            return "Excel Tablosu"
        elif ext in {'.png', '.jpg', '.jpeg', '.tiff', '.bmp'}:
            return "Görsel Dosya"
        else:
            return "Bilinmeyen"

    def validate(self, filename: str, file_size_bytes: int) -> dict[str, Any]:
        errors = []
        
        sanitized_name = self.validate_filename(filename)
        
        if not self.validate_extension(sanitized_name):
            errors.append(f"İzin verilmeyen dosya uzantısı: {Path(sanitized_name).suffix}")
            
        if not self.validate_size(file_size_bytes):
            errors.append(f"Dosya boyutu {self.max_file_size_mb} MB sınırını aşıyor.")
            
        is_valid = len(errors) == 0
        
        return {
            "valid": is_valid,
            "errors": errors,
            "sanitized_name": sanitized_name
        }
