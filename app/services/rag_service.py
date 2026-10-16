"""TF-IDF tabanli mevzuat arama servisi (RAG)."""
import json
import os
import pickle

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from app.config import get_settings


class RAGService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
        return cls._instance

    def __init__(self):
        if not self._loaded:
            self._load_index()
            self._loaded = True

    def _load_index(self):
        settings = get_settings()
        index_dir = settings.RAG_INDEX_DIR

        chunks_path = os.path.join(index_dir, "chunks.json")
        index_path = os.path.join(index_dir, "tfidf.pkl")

        if not os.path.exists(chunks_path) or not os.path.exists(index_path):
            self.chunks = []
            self.vectorizer = None
            self.matrix = None
            self.available = False
            return

        with open(chunks_path, "r", encoding="utf-8") as f:
            self.chunks = json.load(f)

        with open(index_path, "rb") as f:
            data = pickle.load(f)
            self.vectorizer = data["vectorizer"]
            self.matrix = data["matrix"]

        self.chunk_map = {c["id"]: c for c in self.chunks}
        self.available = True

    def search(self, query, top_k=None, doc_type=None):
        if not self.available:
            return []

        settings = get_settings()
        if top_k is None:
            top_k = settings.RAG_TOP_K

        query_vec = self.vectorizer.transform([query])
        scores = cosine_similarity(query_vec, self.matrix).flatten()

        if doc_type:
            for i, chunk in enumerate(self.chunks):
                if chunk.get("type") != doc_type:
                    scores[i] *= 0.5

        top_indices = np.argsort(scores)[::-1][:top_k * 2]
        results = []
        seen_titles = set()

        for idx in top_indices:
            if scores[idx] < 0.05:
                break
            chunk = self.chunks[idx]
            title = chunk["title"]
            if title in seen_titles and len(results) >= top_k // 2:
                continue
            seen_titles.add(title)
            results.append({
                "title": chunk["title"],
                "text": chunk["text"][:1500],
                "score": float(scores[idx]),
                "type": chunk["type"],
                "source": chunk["source"],
                "chunk_index": chunk["chunk_index"],
            })
            if len(results) >= top_k:
                break

        return results

    def search_multi(self, queries, top_k=None):
        if not queries:
            return []
        all_results = {}
        per_query_k = max(3, (top_k or 8) // len(queries) + 1)

        for query in queries:
            for result in self.search(query, top_k=per_query_k):
                key = (result["title"], result["chunk_index"])
                if key not in all_results or result["score"] > all_results[key]["score"]:
                    all_results[key] = result

        sorted_results = sorted(all_results.values(), key=lambda x: x["score"], reverse=True)
        return sorted_results[:top_k or 8]
