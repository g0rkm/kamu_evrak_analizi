# PLAN 1: RAG (Retrieval-Augmented Generation) Sistemi

## Amac
Mevcut LegislationAgent sadece 38 satirlik statik JSON'u LLM prompt'una gomup gonderiyor.
Bunun yerine scraped mevzuat icerigini chunk'layip TF-IDF tabanli bir retrieval sistemi kuracagiz.
Boylece evrak metni icin en ilgili mevzuat parcalarini bulup LLM'e sadece bunlari gondererek
hem kaliteyi hem de baglam penceresi verimliligini arttiracagiz.

## Neden TF-IDF (Dense Embedding Degil)
- Ek bagimliligi minimum (scikit-learn yeterli, GPU / sentence-transformers / Qdrant gereksiz)
- Turkce hukuk metinleri icin BM25/TF-IDF cok etkili (terim bazli eslesme)
- Basit, hizli, ayaga kalkması kolay
- Ilerde dense embedding eklemek icin temel altyapi yine kullanilir

## Mimari

```
documents.json (956 belge)
        |
        v
scripts/build_index.py  -->  app/data/rag/chunks.json   (chunk'lanmis metinler)
                         -->  app/data/rag/tfidf.pkl     (TF-IDF matrisi + vectorizer)
        |
        v
app/services/rag_service.py  (arama motoru: query -> top-k chunks)
        |
        v
app/agents/legislation_agent.py  (RAG sonuclarini LLM prompt'una gomer)
```

## Dosya Degisiklikleri

### 1. YENi: scripts/build_index.py
Gorev: Scraped verileri chunk'la ve TF-IDF indeksi olustur.

- `app/data/scraped/documents.json` oku
- Her belgeyi 500-800 kelimelik parcalara bol (100 kelime overlap)
- Her chunk icin metadata tut: kaynak baslik, belge turu, chunk sirasi
- chunks.json olarak kaydet
- scikit-learn TfidfVectorizer ile tum chunk'lari vektorlestir
- Vectorizer + matris + chunk metadata'yi pickle olarak kaydet (tfidf.pkl)

Cikti dosyalari:
- `app/data/rag/chunks.json` — [{id, title, type, chunk_index, text}, ...]
- `app/data/rag/tfidf.pkl` — {vectorizer: TfidfVectorizer, matrix: sparse_matrix, chunk_ids: [...]}

### 2. YENI: app/services/rag_service.py
Gorev: TF-IDF indeksini yukle ve sorgu yapmak icin arayuz sun.

```python
class RAGService:
    def __init__(self):
        self._load_index()  # tfidf.pkl ve chunks.json yukle
    
    def search(self, query: str, top_k: int = 5, doc_type: str = None) -> list[dict]:
        """Sorguya en yakin chunk'lari dondur.
        
        Returns: [{title, text, score, type, chunk_index}, ...]
        """
        # TF-IDF cosine similarity ile arama
        # Opsiyonel: doc_type filtresi (sadece ilgili turde ara)
    
    def search_multi(self, queries: list[str], top_k: int = 5) -> list[dict]:
        """Birden fazla sorgu ile arama yap, sonuclari birlestir (KADIM'den esinlenerek)."""
```

### 3. DEGISECEK: app/agents/legislation_agent.py
Mevcut: Tum legislation.json'u prompt'a gomiyor
Yeni: RAGService.search() ile en ilgili 5-8 chunk'i bul, sadece bunlari prompt'a gom

```python
class LegislationAgent(BaseAgent):
    def __init__(self, llm_service):
        super().__init__(name="LegislationAgent", llm_service=llm_service)
        self.rag_service = RAGService()
        self.legislation_db = self._load_legislation()  # Hala tut, metadata icin
    
    async def execute(self, text: str, document_type: str = "", keywords: list[str] = []) -> list[LegislationMatch]:
        # 1. Evrak metninden arama sorgusu olustur
        query = self._build_query(text, document_type, keywords)
        
        # 2. RAG ile en ilgili mevzuat parcalarini bul
        rag_results = self.rag_service.search(query, top_k=8)
        
        # 3. Bulunan parcalari + legislation metadata'yi LLM prompt'una gom
        context = self._format_rag_context(rag_results)
        
        # 4. LLM'den eslestirme yap
        ...
```

### 4. DEGISECEK: app/agents/orchestrator.py
LegislationAgent.execute() cagrisi artik keywords parametresi de alacak:
```python
legislation_matches = await self.legislation.execute(
    text=text, 
    document_type=classification.document_type,
    keywords=analysis_data["keywords"]
)
```

### 5. DEGISECEK: app/config.py
Yeni ayarlar:
```python
RAG_INDEX_DIR: str = "app/data/rag"
RAG_TOP_K: int = 8
RAG_CHUNK_SIZE: int = 600  # kelime
RAG_CHUNK_OVERLAP: int = 100  # kelime
```

### 6. DEGISECEK: requirements.txt
Eklenecek:
```
scikit-learn>=1.3.0
```

## Islem Sirasi (Aider Cagrilari)

1. `requirements.txt` + `app/config.py` guncelle (RAG ayarlari + scikit-learn)
2. `scripts/build_index.py` olustur (chunk + indeks)
3. `app/services/rag_service.py` olustur (arama motoru)
4. `app/agents/legislation_agent.py` guncelle (RAG entegrasyonu)
5. `app/agents/orchestrator.py` guncelle (keywords parametresi)
6. `scripts/build_index.py` calistir, indeks olustur
7. Test: sunucuyu baslat, mevzuat eslestirme sonuclarini kontrol et

## Basari Kriteri
- `scripts/build_index.py` calisip chunks.json ve tfidf.pkl olusturmali
- RAGService.search("devlet memuru izin hakki") ilgili sonuclar dondurmeli
- LegislationAgent RAG sonuclarini kullanarak daha hedefli eslestirmeler yapmali
- Mevcut pipeline calismaya devam etmeli (geriye uyumluluk)
