"""HuggingFace'ten korpusu indirip RAG indeksini yerel makinede kurar.

Korpus (taranmış kamu belgeleri) boyut nedeniyle git deposuna dahil edilmez;
HuggingFace dataset'i ``g0rkm/kamu-evrak-korpus`` içinde ``documents.json``
olarak yayımlanır. RAG indeksi (``chunks.json`` + ``tfidf.pkl``) güvenlik
nedeniyle (``tfidf.pkl`` bir pickle; yüklenirken kod çalıştırma riski) HF'e
yüklenmez; bu betik korpusu indirdikten sonra indeksi
``scripts/build_index.py`` ile yerelde üretir.

Kullanım:
    python scripts/setup_data.py          # korpus yoksa indir + indeksi kur
    python scripts/setup_data.py --force  # korpusu yeniden indir

Farklı bir dataset için ``HF_DATASET_REPO`` ortam değişkenini ayarlayın.
"""
import argparse
import os
import shutil
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_REPO = "g0rkm/kamu-evrak-korpus"
FILENAME = "documents.json"
SCRAPED_DIR = BASE_DIR / "app" / "data" / "scraped"
TARGET_PATH = SCRAPED_DIR / FILENAME


def download_corpus(repo_id: str, force: bool) -> None:
    """Korpusu HF dataset'inden ``app/data/scraped/documents.json`` konumuna indirir."""
    if TARGET_PATH.exists() and not force:
        print(f"[=] Korpus zaten mevcut: {TARGET_PATH}")
        print("    (yeniden indirmek icin: python scripts/setup_data.py --force)")
        return

    SCRAPED_DIR.mkdir(parents=True, exist_ok=True)

    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        print("[!] huggingface_hub kurulu degil.")
        print("    Kurulum: pip install huggingface_hub")
        sys.exit(1)

    print(f"[*] Korpus indiriliyor: {repo_id}/{FILENAME} ...")
    try:
        downloaded = hf_hub_download(
            repo_id=repo_id,
            filename=FILENAME,
            repo_type="dataset",
            local_dir=str(SCRAPED_DIR),
        )
    except Exception as exc:  # ag/depo/yetki hatalari
        print(f"[!] Indirme basarisiz: {exc}")
        print("[!] Alternatif: python scripts/scraper.py ile korpusu yeniden uretebilirsiniz.")
        sys.exit(1)

    downloaded_path = Path(downloaded)
    if downloaded_path.resolve() != TARGET_PATH.resolve():
        shutil.copyfile(downloaded_path, TARGET_PATH)

    print(f"[OK] Korpus indirildi: {TARGET_PATH}")


def build_rag_index() -> None:
    """``scripts/build_index.py`` icindeki build() ile TF-IDF indeksini olusturur."""
    print("[*] RAG indeksi kuruluyor (build_index.py) ...")
    scripts_dir = str(BASE_DIR / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    from build_index import build

    build()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="HuggingFace korpusunu indirip RAG indeksini kurar."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Korpus zaten varsa bile yeniden indir.",
    )
    args = parser.parse_args()

    # build_index.py goreli yollar kullandigi icin kok dizine gec.
    os.chdir(BASE_DIR)
    repo_id = os.environ.get("HF_DATASET_REPO", DEFAULT_REPO)

    download_corpus(repo_id, args.force)
    build_rag_index()
    print("[OK] Veri kurulumu tamamlandi.")


if __name__ == "__main__":
    main()
