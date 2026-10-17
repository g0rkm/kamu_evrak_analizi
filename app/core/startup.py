"""Uygulama başlangıcında ortam sağlığını doğrulayan kontroller."""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

from app.config import Settings

logger = logging.getLogger("startup")


def verify_environment(settings: Settings) -> list[str]:
    """Kritik gereksinimleri kontrol eder, uyarı listesi döndürür.

    Hiçbir kontrol uygulamayı durdurmaz; yalnızca uyarı loglanır.
    Böylece LLM olmadan da OCR veya geçmiş görüntüleme kullanılabilir.
    """
    warnings: list[str] = []

    # LLM yapılandırması
    if not settings.LLM_API_KEY or settings.LLM_API_KEY == "not-set":
        warnings.append("LLM_API_KEY ayarlanmamış — evrak analizi çalışmayacak.")

    # Tesseract OCR
    if not shutil.which(settings.TESSERACT_CMD):
        warnings.append(f"Tesseract bulunamadı ('{settings.TESSERACT_CMD}') — PDF ve görüntü dosyaları işlenemeyecek.")

    # Yazılabilir dizinler
    for label, path_str in [("Geçmiş", settings.HISTORY_DIR), ("Yükleme", settings.UPLOAD_DIR)]:
        path = settings.resolve(path_str)
        try:
            path.mkdir(parents=True, exist_ok=True)
            probe = path / ".write_test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
        except OSError as exc:
            warnings.append(f"{label} dizini yazılamıyor ({path}): {exc}")

    # RAG indeksi
    rag_path = settings.rag_index_path
    if not (rag_path / "tfidf_matrix.npz").exists():
        warnings.append("RAG indeksi bulunamadı — mevzuat eşleştirme yalnızca metadata ile çalışacak.")

    # Disk alanı kontrolü
    try:
        import shutil
        disk = shutil.disk_usage(settings.history_path)
        free_mb = disk.free / (1024 * 1024)
        if free_mb < 100:
            warnings.append(f"Disk alanı kritik düzeyde düşük: {free_mb:.0f} MB kaldı")
    except OSError:
        pass

    for w in warnings:
        logger.warning("⚠ %s", w)

    if not warnings:
        logger.info("Ortam doğrulaması tamamlandı — tüm kontroller başarılı.")

    return warnings
