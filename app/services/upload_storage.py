"""Yüklenen dosyaların doğrulanması ve geçici olarak saklanması."""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePath

from fastapi import UploadFile

from app.core.exceptions import FileTooLargeError, InvalidInputError, UnsupportedFileTypeError

logger = logging.getLogger("upload_storage")

ALLOWED_EXTENSIONS = frozenset({".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".txt", ".md"})

MAGIC_BYTES: dict[str, list[bytes]] = {
    ".pdf": [b"%PDF"],
    ".png": [b"\x89PNG"],
    ".jpg": [b"\xff\xd8\xff"],
    ".jpeg": [b"\xff\xd8\xff"],
    ".tif": [b"II\x2a\x00", b"MM\x00\x2a"],
    ".tiff": [b"II\x2a\x00", b"MM\x00\x2a"],
    ".bmp": [b"BM"],
}


@dataclass(frozen=True)
class StoredFile:
    path: Path
    original_name: str
    size: int


class UploadStorage:
    """Dosyaları kullanıcıdan gelen adla değil, rastgele bir adla diske yazar.

    Böylece `../../` içeren dosya adlarıyla dizin dışına yazma (path traversal)
    mümkün olmaz. `keep_files=False` iken dosyalar analizden sonra silinir (KVKK).
    """

    CHUNK_SIZE = 1024 * 1024

    def __init__(self, directory: Path, max_bytes: int, keep_files: bool = False) -> None:
        self.directory = Path(directory)
        self.max_bytes = max_bytes
        self.keep_files = keep_files
        self.directory.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def display_name(filename: str | None) -> str:
        name = PurePath((filename or "").replace("\\", "/")).name.strip()
        return name[:200] or "adsiz_dosya"

    def validate_name(self, filename: str | None) -> tuple[str, str]:
        name = self.display_name(filename)
        extension = PurePath(name).suffix.lower()
        if extension not in ALLOWED_EXTENSIONS:
            allowed = ", ".join(sorted(e.lstrip(".").upper() for e in ALLOWED_EXTENSIONS))
            raise UnsupportedFileTypeError(f"'{extension or 'uzantısız'}' türü desteklenmiyor. Desteklenen türler: {allowed}.")
        return name, extension

    async def save(self, upload: UploadFile) -> StoredFile:
        name, extension = self.validate_name(upload.filename)
        target = self.directory / f"{uuid.uuid4().hex}{extension}"
        size = 0
        try:
            with target.open("wb") as out:
                while chunk := await upload.read(self.CHUNK_SIZE):
                    size += len(chunk)
                    if size > self.max_bytes:
                        raise FileTooLargeError(
                            f"Dosya boyutu {self.max_bytes // (1024 * 1024)} MB sınırını aşıyor."
                        )
                    out.write(chunk)
        except Exception:
            target.unlink(missing_ok=True)
            raise
        if size == 0:
            target.unlink(missing_ok=True)
            raise InvalidInputError("Yüklenen dosya boş.")
        self._verify_magic(target, extension)
        return StoredFile(path=target, original_name=name, size=size)

    @staticmethod
    def _verify_magic(path: Path, extension: str) -> None:
        """Dosya icerigi ile uzantinin tutarliligini kontrol eder."""
        signatures = MAGIC_BYTES.get(extension)
        if not signatures:
            return
        try:
            header = path.read_bytes()[:8]
        except OSError:
            return
        if not any(header.startswith(sig) for sig in signatures):
            raise UnsupportedFileTypeError(
                f"Dosya içeriği '{extension}' uzantısıyla uyuşmuyor. Dosyanın bozuk olmadığından emin olun."
            )

    def release(self, stored: StoredFile) -> None:
        if self.keep_files:
            return
        try:
            stored.path.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("Geçici dosya silinemedi (%s): %s", stored.path.name, exc)
