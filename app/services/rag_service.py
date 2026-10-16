"""TF-IDF tabanlı mevzuat arama servisi (RAG)."""
from __future__ import annotations

import json
import logging
import pickle
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from app.config import Settings, get_settings

logger = logging.getLogger("rag_service")


@dataclass(frozen=True)
class RetrievedChunk:
    title: str
    text: str
    score: float
    type: str
    source: str
    chunk_index: int


class RAGService:
    """`scripts/build_index.py` ile üretilen indeksi yükler ve arama yapar.

    İndeks yoksa servis `available=False` durumuna geçer ve boş sonuç döndürür;
    uygulama RAG olmadan da çalışmaya devam eder.
    """

    MIN_SCORE = 0.05
    TEXT_PREVIEW_CHARS = 1500

    _shared: RAGService | None = None

    def __init__(self, index_dir: str | Path | None = None, top_k: int | None = None) -> None:
        settings: Settings = get_settings()
        self.index_dir = Path(index_dir) if index_dir else settings.rag_index_path
        self.default_top_k = top_k or settings.RAG_TOP_K
        self.chunks: list[dict] = []
        self.vectorizer = None
        self.matrix = None
        self.available = False
        self._load_index()

    @classmethod
    def shared(cls) -> RAGService:
        """İndeksi tek bir kez belleğe yükleyen paylaşılan örnek."""
        if cls._shared is None:
            cls._shared = cls()
        return cls._shared

    @property
    def chunk_count(self) -> int:
        return len(self.chunks)

    def _load_index(self) -> None:
        chunks_path = self.index_dir / "chunks.json"
        index_path = self.index_dir / "tfidf.pkl"
        if not chunks_path.exists() or not index_path.exists():
            logger.info("RAG indeksi bulunamadı (%s); mevzuat araması devre dışı", self.index_dir)
            return

        with chunks_path.open("r", encoding="utf-8") as f:
            self.chunks = json.load(f)
        with index_path.open("rb") as f:
            data = pickle.load(f)  # Yerel, güvenilir indeks dosyası
        self.vectorizer = data["vectorizer"]
        self.matrix = data["matrix"]
        self.available = True
        logger.info("RAG indeksi yüklendi: %d parça", len(self.chunks))

    def search(self, query: str, top_k: int | None = None, doc_type: str | None = None) -> list[RetrievedChunk]:
        if not self.available or not query.strip():
            return []
        top_k = top_k or self.default_top_k

        scores = cosine_similarity(self.vectorizer.transform([query]), self.matrix).flatten()
        if doc_type:
            for i, chunk in enumerate(self.chunks):
                if chunk.get("type") != doc_type:
                    scores[i] *= 0.5

        results: list[RetrievedChunk] = []
        seen_titles: set[str] = set()
        for idx in np.argsort(scores)[::-1][: top_k * 2]:
            if scores[idx] < self.MIN_SCORE:
                break
            chunk = self.chunks[idx]
            title = chunk["title"]
            if title in seen_titles and len(results) >= top_k // 2:
                continue
            seen_titles.add(title)
            results.append(RetrievedChunk(
                title=title,
                text=chunk["text"][: self.TEXT_PREVIEW_CHARS],
                score=float(scores[idx]),
                type=chunk.get("type", ""),
                source=chunk.get("source", ""),
                chunk_index=chunk.get("chunk_index", 0),
            ))
            if len(results) >= top_k:
                break
        return results

    def search_multi(self, queries: list[str], top_k: int | None = None) -> list[RetrievedChunk]:
        """Birden çok sorgunun sonuçlarını birleştirir, tekrarları en yüksek skorla tutar."""
        if not queries:
            return []
        top_k = top_k or self.default_top_k
        per_query_k = max(3, top_k // len(queries) + 1)

        best: dict[tuple[str, int], RetrievedChunk] = {}
        for query in queries:
            for hit in self.search(query, top_k=per_query_k):
                key = (hit.title, hit.chunk_index)
                if key not in best or hit.score > best[key].score:
                    best[key] = hit
        return sorted(best.values(), key=lambda h: h.score, reverse=True)[:top_k]
