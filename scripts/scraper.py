import json
import os
import sys
import asyncio
import tempfile
import pymupdf
from datetime import date, timedelta
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
            async with page.expect_download(timeout=30000) as download_info:
                try:
                    await page.goto(url)
                except Exception:
                    pass
            download = await download_info.value

            tmp_file = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
            tmp_path = tmp_file.name
            tmp_file.close()
            await download.save_as(tmp_path)

            doc = pymupdf.open(tmp_path)
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
        t = title.lower()
        if "yönetmelik" in t:
            return "yonetmelik"
        elif "tebliğ" in t:
            return "teblig"
        elif "genelge" in t:
            return "genelge"
        elif "kararname" in t:
            return "kararname"
        elif "karar" in t:
            return "karar"
        elif "kanun" in t:
            return "kanun"
        elif "ilan" in t or "duyuru" in t:
            return "ilan"
        elif "usul" in t and "esas" in t:
            return "usul_esaslar"
        elif "yönerge" in t:
            return "yonerge"
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

    async def scrape_law(self, page, mevzuat_no, mevzuat_tur=1, mevzuat_tertip=5, label=""):
        try:
            url = (
                f"{self.base_url}/anasayfa/MevzuatFihristDetayIframe"
                f"?MevzuatTur={mevzuat_tur}&MevzuatNo={mevzuat_no}"
                f"&MevzuatTertip={mevzuat_tertip}"
            )
            await page.goto(url, timeout=30000)
            await page.wait_for_timeout(10000)

            full_text = await page.inner_text("body")
            if not full_text:
                return None

            full_text = full_text.strip()
            if len(full_text) < 200:
                print(f"    [!] Cok kisa metin ({len(full_text)} kar), atlanıyor")
                return None

            lines = [line.strip() for line in full_text.split('\n') if line.strip()]
            title = lines[0] if lines else f"Mevzuat No: {mevzuat_no}"

            tur_map = {1: "kanun", 19: "cumhurbaskanligi_kararnamesi", 4: "khk", 7: "tuzuk"}
            doc_type = tur_map.get(mevzuat_tur, "mevzuat")

            return {
                "id": f"mv_{doc_type}_{mevzuat_no}",
                "source": "mevzuat_gov_tr",
                "mevzuat_no": mevzuat_no,
                "mevzuat_tur": mevzuat_tur,
                "type": doc_type,
                "title": title,
                "content": full_text[:50000],
                "char_count": len(full_text[:50000])
            }
        except Exception as e:
            print(f"  [MV] Mevzuat hata (No: {mevzuat_no}): {e}")
            return None


def generate_rg_dates():
    dates = []
    for year in range(2024, 2027):
        end_month = 10 if year == 2026 else 12
        for month in range(1, end_month + 1):
            for day in [3, 13, 23]:
                try:
                    d = date(year, month, day)
                    if d.weekday() == 5:
                        d += timedelta(days=2)
                    elif d.weekday() == 6:
                        d += timedelta(days=1)
                    if d <= date(2026, 10, 14):
                        dates.append(d.strftime("%Y-%m-%d"))
                except ValueError:
                    pass
    return dates


KANUNLAR = [
    # --- Temel Kamu Hukuku ---
    {"no": 2709, "tur": 1, "tertip": 5, "ad": "T.C. Anayasasi"},
    {"no": 657, "tur": 1, "tertip": 4, "ad": "Devlet Memurlari"},
    {"no": 5018, "tur": 1, "tertip": 5, "ad": "Kamu Mali Yonetimi"},
    {"no": 4734, "tur": 1, "tertip": 5, "ad": "Kamu Ihale"},
    {"no": 2886, "tur": 1, "tertip": 5, "ad": "Devlet Ihale"},
    {"no": 5393, "tur": 1, "tertip": 5, "ad": "Belediye Kanunu"},
    {"no": 5302, "tur": 1, "tertip": 5, "ad": "Il Ozel Idaresi"},
    {"no": 5216, "tur": 1, "tertip": 5, "ad": "Buyuksehir Belediyesi"},
    {"no": 6085, "tur": 1, "tertip": 5, "ad": "Sayistay"},
    {"no": 5442, "tur": 1, "tertip": 4, "ad": "Il Idaresi Kanunu"},

    # --- Temel Hukuk ---
    {"no": 5237, "tur": 1, "tertip": 5, "ad": "Turk Ceza Kanunu"},
    {"no": 5271, "tur": 1, "tertip": 5, "ad": "Ceza Muhakemesi"},
    {"no": 4721, "tur": 1, "tertip": 5, "ad": "Turk Medeni Kanunu"},
    {"no": 6098, "tur": 1, "tertip": 5, "ad": "Turk Borclar Kanunu"},
    {"no": 6100, "tur": 1, "tertip": 5, "ad": "Hukuk Muhakemeleri"},
    {"no": 6102, "tur": 1, "tertip": 5, "ad": "Turk Ticaret Kanunu"},
    {"no": 2004, "tur": 1, "tertip": 3, "ad": "Icra ve Iflas Kanunu"},

    # --- Idari Hukuk ---
    {"no": 2577, "tur": 1, "tertip": 5, "ad": "Idari Yargilama Usulu"},
    {"no": 3071, "tur": 1, "tertip": 5, "ad": "Dilekce Hakki"},
    {"no": 4982, "tur": 1, "tertip": 5, "ad": "Bilgi Edinme Hakki"},
    {"no": 7201, "tur": 1, "tertip": 3, "ad": "Tebligat Kanunu"},
    {"no": 4483, "tur": 1, "tertip": 5, "ad": "Memurlar Hakkinda Kovusturma"},

    # --- Vergi / Mali ---
    {"no": 213, "tur": 1, "tertip": 3, "ad": "Vergi Usul Kanunu"},
    {"no": 193, "tur": 1, "tertip": 3, "ad": "Gelir Vergisi"},
    {"no": 3065, "tur": 1, "tertip": 5, "ad": "KDV Kanunu"},
    {"no": 6245, "tur": 1, "tertip": 3, "ad": "Harcirah Kanunu"},

    # --- Is / Sosyal Guvenlik ---
    {"no": 4857, "tur": 1, "tertip": 5, "ad": "Is Kanunu"},
    {"no": 5510, "tur": 1, "tertip": 5, "ad": "Sosyal Sigortalar"},

    # --- Diger Onemli Kanunlar ---
    {"no": 2547, "tur": 1, "tertip": 5, "ad": "Yuksekogretim"},
    {"no": 3628, "tur": 1, "tertip": 5, "ad": "Mal Bildiriminde Bulunulmasi"},
    {"no": 5176, "tur": 1, "tertip": 5, "ad": "Kamu Gorevlileri Etik Kurulu"},
    {"no": 6698, "tur": 1, "tertip": 5, "ad": "Kisisel Verilerin Korunmasi"},
    {"no": 5070, "tur": 1, "tertip": 5, "ad": "Elektronik Imza"},
    {"no": 1136, "tur": 1, "tertip": 4, "ad": "Avukatlik Kanunu"},
    {"no": 7245, "tur": 1, "tertip": 5, "ad": "Calisanlarin Isverenler Araciligiyla Otomatik Olarak Emeklilik Planina Dahil Edilmesi"},
    {"no": 6325, "tur": 1, "tertip": 5, "ad": "Hukuk Uyusmazliklarinda Arabuluculuk"},
]

CUMHURBASKANLIGI_KARARNAMELERI = [
    {"no": 1, "tur": 19, "tertip": 5, "ad": "CB Teskilati Hakkinda"},
    {"no": 2, "tur": 19, "tertip": 5, "ad": "Genel Kadro ve Usulu"},
    {"no": 3, "tur": 19, "tertip": 5, "ad": "Ust Kademe Kamu Yoneticileri"},
    {"no": 4, "tur": 19, "tertip": 5, "ad": "Bakanliklara Bagli Kuruluslar"},
    {"no": 5, "tur": 19, "tertip": 5, "ad": "Devlet Denetleme Kurulu"},
]


def load_existing(output_path):
    if os.path.exists(output_path):
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def save_documents(all_documents, output_path):
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_documents, f, ensure_ascii=False, indent=2)


def get_scraped_dates(documents):
    return set(d.get("date", "") for d in documents if d.get("source") == "resmi_gazete")


def get_scraped_mevzuat_ids(documents):
    return set(d.get("id", "") for d in documents if d.get("source") == "mevzuat_gov_tr")


async def main():
    output_dir = "app/data/scraped"
    output_path = os.path.join(output_dir, "documents.json")

    all_documents = load_existing(output_path)
    scraped_dates = get_scraped_dates(all_documents)
    scraped_mv_ids = get_scraped_mevzuat_ids(all_documents)

    print(f"[*] Mevcut veri: {len(all_documents)} belge, {len(scraped_dates)} tarih, {len(scraped_mv_ids)} mevzuat")

    dates = generate_rg_dates()
    new_dates = [d for d in dates if d not in scraped_dates]
    print(f"[*] Toplam {len(dates)} tarih, {len(new_dates)} yeni taranacak")

    all_mevzuat = KANUNLAR + CUMHURBASKANLIGI_KARARNAMELERI
    tur_map = {1: "kanun", 19: "cumhurbaskanligi_kararnamesi", 4: "khk", 7: "tuzuk"}

    new_mevzuat = []
    for m in all_mevzuat:
        doc_type = tur_map.get(m["tur"], "mevzuat")
        mv_id = f"mv_{doc_type}_{m['no']}"
        if mv_id not in scraped_mv_ids:
            new_mevzuat.append(m)
    print(f"[*] Toplam {len(all_mevzuat)} mevzuat, {len(new_mevzuat)} yeni taranacak")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(accept_downloads=True)
        page = await context.new_page()

        rg_scraper = ResmiGazeteScraper(output_dir)
        mv_scraper = MevzuatScraper(output_dir)

        for i, d in enumerate(new_dates):
            print(f"[RG {i+1}/{len(new_dates)}] {d} tarihli belgeler taranacak...")
            try:
                docs = await rg_scraper.scrape_date(page, d, include_pdf=True)
                all_documents.extend(docs)
                print(f"  -> {len(docs)} belge cekildi")
            except Exception as e:
                print(f"  -> HATA: {e}")

            if (i + 1) % 5 == 0:
                save_documents(all_documents, output_path)
                print(f"  [Kaydedildi] toplam {len(all_documents)} belge")

            await asyncio.sleep(1)

        for i, law in enumerate(new_mevzuat):
            print(f"[MV {i+1}/{len(new_mevzuat)}] {law['ad']} (No: {law['no']}) cekilecek...")
            try:
                doc = await mv_scraper.scrape_law(
                    page, law["no"], law["tur"], law["tertip"], law["ad"]
                )
                if doc:
                    all_documents.append(doc)
                    print(f"  -> {doc['title'][:60]}... ({doc['char_count']} kar)")
                else:
                    print(f"  -> Metin alinamadi")
            except Exception as e:
                print(f"  -> HATA: {e}")

            await asyncio.sleep(2)

        await context.close()
        await browser.close()

    save_documents(all_documents, output_path)

    print(f"\n{'='*60}")
    print(f"Toplam {len(all_documents)} belge kaydedildi: {output_path}")

    types = {}
    sources = {}
    for doc in all_documents:
        t = doc.get("type", doc.get("source", "unknown"))
        s = doc.get("source", "unknown")
        types[t] = types.get(t, 0) + 1
        sources[s] = sources.get(s, 0) + 1

    print("\nKaynak dagilimi:")
    for s, c in sorted(sources.items()):
        print(f"  {s}: {c}")

    print("\nTur dagilimi:")
    for t, c in sorted(types.items()):
        print(f"  {t}: {c}")


if __name__ == "__main__":
    os.environ["PYTHONUTF8"] = "1"
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = open(sys.stdout.fileno(), mode="w", encoding="utf-8", errors="replace", closefd=False)
    asyncio.run(main())
