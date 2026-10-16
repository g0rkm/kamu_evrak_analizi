"""Scraped mevzuat belgelerini chunk'la ve TF-IDF arama indeksi olustur."""
import json
import os
import pickle
import re
import sys

from sklearn.feature_extraction.text import TfidfVectorizer

SCRAPED_PATH = "app/data/scraped/documents.json"
OUTPUT_DIR = "app/data/rag"
CHUNK_SIZE = 600
CHUNK_OVERLAP = 100


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

    for doc in docs:
        content = doc.get("content", "")
        if not content or len(content) < 200:
            continue

        title = doc.get("title", "Bilinmiyor")
        doc_type = doc.get("type", doc.get("source", "diger"))
        source = doc.get("source", "unknown")
        content = clean_text(content)
        chunks = chunk_text(content)

        for i, chunk_text_val in enumerate(chunks):
            all_chunks.append({
                "id": chunk_id,
                "title": title,
                "type": doc_type,
                "source": source,
                "chunk_index": i,
                "total_chunks": len(chunks),
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
