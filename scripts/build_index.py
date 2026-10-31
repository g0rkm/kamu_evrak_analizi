"""Scraped mevzuat belgelerini chunk'la ve TF-IDF arama indeksi olustur."""
import hashlib
import json
import os
import pickle
import re
import sys
from datetime import datetime, timezone

from sklearn.feature_extraction.text import TfidfVectorizer

# Depo kökünü sys.path'e ekle ki `python scripts/build_index.py` ile de
# `from app...` importları çözülsün (aksi halde yalnizca scripts/ path'te olur).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.core.text_normalize import turkish_lower

SCRAPED_PATH = "app/data/scraped/documents.json"
OUTPUT_DIR = "app/data/rag"
CHUNK_SIZE = 600
CHUNK_OVERLAP = 100


GENERIC_TITLES = {"", "pdf görüntüle", "pdf goruntule", "menü", "menu", "ana sayfa", "başlıksız", "bilinmiyor"}
LAW_NO_RE = re.compile(r"\b(\d{3,5})\s*say[ıi]l[ıi]\b", re.IGNORECASE)
ARTICLE_RE = re.compile(r"\bMadde\s+(\d+)", re.IGNORECASE)


def derive_title(raw_title: str, content: str) -> str:
    """Jenerik/boş başlıkları (`PDF Görüntüle` vb.) içeriğin ilk anlamlı satırıyla değiştirir."""
    t = (raw_title or "").strip()
    if t.lower() not in GENERIC_TITLES and len(t) >= 5:
        return t
    for line in content.splitlines():
        line = line.strip()
        if len(line) >= 10:
            return line[:120]
    return t or "Başlıksız"


def clean_text(text):
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()


def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    words = text.split()
    if len(words) <= chunk_size:
        return [text]
    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        start += chunk_size - overlap
    return chunks


def build():
    print(f"[*] {SCRAPED_PATH} okunuyor...")
    with open(SCRAPED_PATH, "r", encoding="utf-8") as f:
        docs = json.load(f)

    all_chunks = []
    chunk_id = 0
    indexed_at = datetime.now(timezone.utc).isoformat()

    for doc in docs:
        content = doc.get("content", "")
        if not content or len(content) < 200:
            continue

        doc_type = doc.get("type", doc.get("source", "diger"))
        source = doc.get("source", "unknown")
        source_url = doc.get("url", "") or ""
        publish_date = doc.get("date", "") or ""
        doc_key = str(doc.get("id") or doc.get("url") or source)
        content = clean_text(content)
        title = derive_title(doc.get("title", ""), content)
        chunks = chunk_text(content)

        for i, chunk_text_val in enumerate(chunks):
            law_match = LAW_NO_RE.search(chunk_text_val)
            article_refs = sorted(set(ARTICLE_RE.findall(chunk_text_val)), key=int)[:10]
            all_chunks.append({
                "id": chunk_id,
                "chunk_id": f"{doc_key}::{i}",
                "title": title,
                "type": doc_type,
                "source": source,
                "source_url": source_url,
                "publish_date": publish_date,
                "indexed_at": indexed_at,
                "chunk_index": i,
                "total_chunks": len(chunks),
                "law_no": law_match.group(1) if law_match else "",
                "article_refs": article_refs,
                "content_md5": hashlib.md5(chunk_text_val.encode("utf-8")).hexdigest(),
                "text": chunk_text_val,
            })
            chunk_id += 1

    print(f"[*] {len(docs)} belgeden {len(all_chunks)} chunk olusturuldu")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    chunks_path = os.path.join(OUTPUT_DIR, "chunks.json")
    with open(chunks_path, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, ensure_ascii=False)
    print(f"[*] Chunk'lar kaydedildi: {chunks_path}")

    texts = [c["text"] for c in all_chunks]
    vectorizer = TfidfVectorizer(
        preprocessor=turkish_lower,
        lowercase=False,
        max_features=50000,
        ngram_range=(1, 2),
        sublinear_tf=True,
        min_df=2,
        max_df=0.95,
    )
    tfidf_matrix = vectorizer.fit_transform(texts)
    print(f"[*] TF-IDF matrisi: {tfidf_matrix.shape}")

    index_path = os.path.join(OUTPUT_DIR, "tfidf.pkl")
    with open(index_path, "wb") as f:
        pickle.dump({
            "vectorizer": vectorizer,
            "matrix": tfidf_matrix,
            "chunk_ids": [c["id"] for c in all_chunks],
        }, f)
    print(f"[*] Indeks kaydedildi: {index_path}")
    print("[OK] Tamamlandi.")


if __name__ == "__main__":
    build()
