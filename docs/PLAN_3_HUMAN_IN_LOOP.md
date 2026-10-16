# PLAN 3: Human-in-the-Loop (Memur Onay Mekanizmasi)

## Amac
Pipeline sonuclarini (taslak yazi, yonlendirme karari) gosterdikten sonra
kullanicinin "Onayla / Duzenle / Reddet" secimi yapabilmesini saglamak.
KADIM ve AGENTIX projelerinden esinlenerek.

## Kapsam

### Frontend Degisiklikleri

#### 1. Yazi Taslagi sekmesine aksyon butonlari ekle:
- "Onayla" (yesil) — Taslagi onayla, son hali olarak isaretle
- "Duzenle" (mavi) — Taslak govdesini editable hale getir
- "Reddet" (kirmizi) — Reddedildi olarak isaretle, neden gir

#### 2. Yonlendirme sekmesine aksyon butonlari ekle:
- "Onayla" (yesil) — Yonlendirmeyi onayla
- "Degistir" (mavi) — Alternatif birim sec (dropdown)

#### 3. Durum gostergesi:
- Her iki sekmede de "Beklemede / Onaylandi / Reddedildi / Duzenlendi" badge'i

## Dosya Degisiklikleri

### 1. DEGISECEK: frontend/index.html

#### Taslak sekmesine (content-draft) ekle:
```html
<!-- Memur Aksyon Paneli -->
<div id="draftActionPanel" class="hidden mt-4 p-4 rounded-xl bg-slate-50 dark:bg-slate-700/30 border border-slate-200 dark:border-slate-700">
    <div class="flex items-center justify-between mb-3">
        <h4 class="text-sm font-semibold flex items-center gap-2">
            <i class="fa-solid fa-user-check text-blue-500"></i> Memur Karari
        </h4>
        <span id="draftStatusBadge" class="px-2.5 py-1 rounded-full text-xs font-bold bg-amber-100 text-amber-700 dark:bg-amber-900/50 dark:text-amber-300">Beklemede</span>
    </div>
    <div id="draftActionButtons" class="flex gap-3">
        <button id="approveDraftBtn" class="flex-1 py-2 px-4 rounded-lg bg-green-600 hover:bg-green-700 text-white text-sm font-medium transition flex items-center justify-center gap-2">
            <i class="fa-solid fa-check"></i> Onayla
        </button>
        <button id="editDraftBtn" class="flex-1 py-2 px-4 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium transition flex items-center justify-center gap-2">
            <i class="fa-solid fa-pen"></i> Duzenle
        </button>
        <button id="rejectDraftBtn" class="flex-1 py-2 px-4 rounded-lg bg-red-600 hover:bg-red-700 text-white text-sm font-medium transition flex items-center justify-center gap-2">
            <i class="fa-solid fa-xmark"></i> Reddet
        </button>
    </div>
    <!-- Duzenleme alani (gizli) -->
    <div id="draftEditArea" class="hidden mt-3">
        <textarea id="draftEditTextarea" class="w-full p-3 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm min-h-[200px] focus:outline-none focus:ring-2 focus:ring-blue-500"></textarea>
        <div class="flex gap-2 mt-2">
            <button id="saveDraftEditBtn" class="py-2 px-4 rounded-lg bg-green-600 hover:bg-green-700 text-white text-sm font-medium">Kaydet</button>
            <button id="cancelDraftEditBtn" class="py-2 px-4 rounded-lg bg-slate-200 hover:bg-slate-300 dark:bg-slate-600 dark:hover:bg-slate-500 text-sm font-medium">Iptal</button>
        </div>
    </div>
    <!-- Reddetme nedeni (gizli) -->
    <div id="draftRejectArea" class="hidden mt-3">
        <input id="draftRejectReason" type="text" placeholder="Reddetme nedeni..." class="w-full p-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm focus:outline-none focus:ring-2 focus:ring-red-500">
        <button id="confirmRejectBtn" class="mt-2 py-2 px-4 rounded-lg bg-red-600 hover:bg-red-700 text-white text-sm font-medium">Reddi Onayla</button>
    </div>
</div>
```

#### Yonlendirme sekmesine (content-routing) ekle:
```html
<!-- Yonlendirme Onay Paneli -->
<div id="routingActionPanel" class="hidden mt-4 p-4 rounded-xl bg-slate-50 dark:bg-slate-700/30 border border-slate-200 dark:border-slate-700">
    <div class="flex items-center justify-between mb-3">
        <h4 class="text-sm font-semibold flex items-center gap-2">
            <i class="fa-solid fa-user-check text-blue-500"></i> Yonlendirme Karari
        </h4>
        <span id="routingStatusBadge" class="px-2.5 py-1 rounded-full text-xs font-bold bg-amber-100 text-amber-700 dark:bg-amber-900/50 dark:text-amber-300">Beklemede</span>
    </div>
    <div id="routingActionButtons" class="flex gap-3">
        <button id="approveRoutingBtn" class="flex-1 py-2 px-4 rounded-lg bg-green-600 hover:bg-green-700 text-white text-sm font-medium transition flex items-center justify-center gap-2">
            <i class="fa-solid fa-check"></i> Onayla
        </button>
        <button id="changeRoutingBtn" class="flex-1 py-2 px-4 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium transition flex items-center justify-center gap-2">
            <i class="fa-solid fa-arrow-right-arrow-left"></i> Birimi Degistir
        </button>
    </div>
    <!-- Birim degistirme (gizli) -->
    <div id="routingChangeArea" class="hidden mt-3">
        <select id="routingUnitSelect" class="w-full p-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm">
            <option value="">Birim secin...</option>
            <option value="Hukuk Musavirligi">Hukuk Musavirligi</option>
            <option value="Insan Kaynaklari Daire Baskanligi">Insan Kaynaklari Daire Baskanligi</option>
            <option value="Strateji Gelistirme Daire Baskanligi">Strateji Gelistirme Daire Baskanligi</option>
            <option value="Bilgi Teknolojileri Daire Baskanligi">Bilgi Teknolojileri Daire Baskanligi</option>
            <option value="Idari ve Mali Isler Daire Baskanligi">Idari ve Mali Isler Daire Baskanligi</option>
            <option value="Basin ve Halkla Iliskiler Mudurlugu">Basin ve Halkla Iliskiler Mudurlugu</option>
            <option value="Teftis Kurulu Baskanligi">Teftis Kurulu Baskanligi</option>
            <option value="Genel Mudurluk">Genel Mudurluk</option>
        </select>
        <button id="confirmRoutingChangeBtn" class="mt-2 py-2 px-4 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium">Degisikligi Kaydet</button>
    </div>
</div>
```

### 2. DEGISECEK: frontend/app.js

#### renderDraft fonksiyonuna ekle:
- `draftActionPanel` goster
- Buton click handler'lari:
  - approveDraftBtn: badge "Onaylandi" (yesil), butonlari gizle
  - editDraftBtn: draftEditArea goster, mevcut body'yi textarea'ya koy
  - rejectDraftBtn: draftRejectArea goster
  - saveDraftEditBtn: textarea icerigini draftBody'ye yansit, badge "Duzenlendi" (mavi)
  - confirmRejectBtn: badge "Reddedildi" (kirmizi), butonlari gizle

#### renderRouting fonksiyonuna ekle:
- `routingActionPanel` goster
- Buton click handler'lari:
  - approveRoutingBtn: badge "Onaylandi" (yesil)
  - changeRoutingBtn: routingChangeArea goster
  - confirmRoutingChangeBtn: secili birimi targetUnit'e yansit, badge "Degistirildi" (mavi)

## Islem Sirasi (Aider Cagrilari)

1. `frontend/index.html` guncelle (aksyon panelleri HTML)
2. `frontend/app.js` guncelle (event handler'lar ve durum yonetimi)
3. Test: analiz calistir, taslak/yonlendirme sekmelerinde butonlari test et

## Basari Kriteri
- Analiz tamamlandiktan sonra taslak sekmesinde "Onayla/Duzenle/Reddet" butonlari gorunmeli
- "Duzenle" tiklaninca taslak metni editable olmali ve kaydedilebilmeli
- "Reddet" tiklaninca neden girilebilmeli
- Yonlendirme sekmesinde "Onayla/Degistir" butonlari calismali
- Birim degistirince UI aninda guncellenmeli
- Tum state client-side (localStorage veya JS degiskeni) tutulmali
