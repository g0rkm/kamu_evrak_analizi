import json
import os
import sys
import asyncio
import tempfile
import fitz  # pymupdf
from datetime import datetime
from playwright.async_api import async_playwright

class ResmiGazeteScraper:
    def __init__(self, output_dir="app/data/scraped"):
        self.output_dir = output_dir
        self.base_url = "https://www.resmigazete.gov.tr"
        os.makedirs(output_dir, exist_ok=True)

    async def get_fihrist(self, page, tarih_str):
        try:
            url = f"{self.base_url}/fihrist?tarih={tarih_str}"
            await page.goto(url, timeout=30000)
            await page.wait_for_load_state("networkidle")
            
            links = await page.locator('a[href*="eskiler"]').all()
            documents = []
            
            for link in links:
                try:
                    title = await link.inner_text()
                    title = title.strip()
                    if len(title) <= 10:
                        continue
                    
                    href = await link.get_attribute("href")
                    if not href:
                        continue
                        
                    if href.startswith("/"):
                        href = self.base_url + href
                    elif not href.startswith("http"):
                        href = f"{self.base_url}/{href}"
                        
                    doc_type = "pdf" if href.lower().endswith(".pdf") else "htm"
                    
                    documents.append({
                        "title": title,
                        "url": href,
                        "type": doc_type,
                        "date": tarih_str
                    })
                except Exception:
                    continue
            return documents
        except Exception as e:
            print(f"  [RG] Fihrist hata ({tarih_str}): {e}")
            return []

    async def scrape_htm_document(self, page, url):
        try:
            response = await page.goto(url, timeout=30000)
            if response and response.ok:
                await page.wait_for_load_state("networkidle")
                text = await page.inner_text("body")
                if text:
                    return text.strip()[:50000]
        except Exception as e:
            print(f"  [RG] HTM hata ({url}): {e}")
        return None

    async def scrape_pdf_document(self, page, url):
        try:
            response = await page.goto(url, timeout=30000)
            if response and response.ok:
                body = await response.body()
                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                    tmp.write(body)
                    tmp_path = tmp.name
                
                doc = fitz.open(tmp_path)
                text = ""
                for p in doc:
                    text += p.get_text()
                doc.close()
                os.unlink(tmp_path)
                
                text = text.strip()
                if len(text) < 100:
                    return None
                return text[:50000]
        except Exception as e:
            print(f"  [RG] PDF hata ({url}): {e}")
            return None

    def determine_type(self, title):
        t_lower = title.lower()
        if "yönetmelik" in t_lower:
            return "yonetmelik"
        elif "tebliğ" in t_lower:
            return "teblig"
        elif "genelge" in t_lower:
            return "genelge"
        elif "karar" in t_lower:
            return "karar"
        elif "kanun" in t_lower:
            return "kanun"
        return "diger"

    async def scrape_date(self, page, tarih_str, include_pdf=True):
        fihrist_items = await self.get_fihrist(page, tarih_str)
        documents = []
        
        for index, item in enumerate(fihrist_items):
            url = item["url"]
            title = item["title"]
            doc_type = item["type"]
            
            full_text = None
            if doc_type == "htm":
                full_text = await self.scrape_htm_document(page, url)
            elif doc_type == "pdf" and include_pdf:
                full_text = await self.scrape_pdf_document(page, url)
                
            if not full_text:
                continue
                
            category_type = self.determine_type(title)
            
            documents.append({
                "id": f"rg_{tarih_str}_{index}",
                "source": "resmi_gazete",
                "date": tarih_str,
                "title": title,
                "url": url,
                "type": category_type,
                "content": full_text,
                "char_count": len(full_text)
            })
        return documents


class MevzuatScraper:
    def __init__(self, output_dir="app/data/scraped"):
        self.output_dir = output_dir
        self.base_url = "https://www.mevzuat.gov.tr"
        os.makedirs(output_dir, exist_ok=True)

    async def scrape_law(self, page, mevzuat_no, mevzuat_tur=1, mevzuat_tertip=5):
        try:
            url = f"{self.base_url}/anasayfa/MevzuatFihristDetayIframe?MevzuatTur={mevzuat_tur}&MevzuatNo={mevzuat_no}&MevzuatTertip={mevzuat_tertip}"
            await page.goto(url, timeout=30000)
            await page.wait_for_timeout(5000)
            
            full_text = await page.inner_text("body")
            if not full_text:
                return None
                
            full_text = full_text.strip()
            lines = [line.strip() for line in full_text.split('\n') if line.strip()]
            title = lines[0] if lines else f"Mevzuat No: {mevzuat_no}"
            
            return {
                "id": f"mv_{mevzuat_no}",
                "source": "mevzuat_gov_tr",
                "mevzuat_no": mevzuat_no,
                "mevzuat_tur": mevzuat_tur,
                "title": title,
                "content": full_text[:50000],
                "char_count": len(full_text[:50000])
            }
        except Exception as e:
            print(f"  [MV] Mevzuat hata (No: {mevzuat_no}): {e}")
            return None


async def main():
    DATES = [
        "2024-05-17",
        "2024-11-26",
        "2025-01-16",
        "2024-09-15",
        "2025-03-01",
        "2024-06-14",
        "2024-08-10",
        "2025-05-20",
        "2025-07-15",
        "2026-01-10",
    ]

    LAWS = [
        {"no": 657, "tur": 1, "tertip": 5},
        {"no": 5018, "tur": 1, "tertip": 5},
        {"no": 4734, "tur": 1, "tertip": 5},
        {"no": 3071, "tur": 1, "tertip": 5},
        {"no": 7201, "tur": 1, "tertip": 5},
        {"no": 2577, "tur": 1, "tertip": 5},
    ]

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()

        rg_scraper = ResmiGazeteScraper()
        mv_scraper = MevzuatScraper()

        all_documents = []

        for date in DATES:
            print(f"[RG] {date} tarihli belgeler taranacak...")
            try:
                docs = await rg_scraper.scrape_date(page, date, include_pdf=True)
                all_documents.extend(docs)
                print(f"  -> {len(docs)} belge cekildi")
            except Exception as e:
                print(f"  -> HATA: {e}")

        for law in LAWS:
            print(f"[MV] Mevzuat No: {law['no']} cekilecek...")
            try:
                doc = await mv_scraper.scrape_law(page, law["no"], law["tur"], law["tertip"])
                if doc:
                    all_documents.append(doc)
                    print(f"  -> {doc['title'][:60]}... ({doc['char_count']} karakter)")
            except Exception as e:
                print(f"  -> HATA: {e}")

        await browser.close()

        output_path = os.path.join(rg_scraper.output_dir, "documents.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(all_documents, f, ensure_ascii=False, indent=2)

        print(f"\nToplam {len(all_documents)} belge kaydedildi: {output_path}")

        types = {}
        for doc in all_documents:
            t = doc.get("type", doc.get("source", "unknown"))
            types[t] = types.get(t, 0) + 1
        print("Tur dagilimi:")
        for t, c in sorted(types.items()):
            print(f"  {t}: {c}")


if __name__ == "__main__":
    os.environ["PYTHONUTF8"] = "1"
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = open(sys.stdout.fileno(), mode="w", encoding="utf-8", errors="replace", closefd=False)
    asyncio.run(main())
