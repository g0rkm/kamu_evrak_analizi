// Arka uçtan (/api/meta) gelen sözlük + arayüz metinleri ve biçimlendiriciler.

const FALLBACK_META = {
    document_types: [],
    units: [],
    draft_types: [],
    priorities: [],
    pipeline_steps: [
        { key: 'extract', label: 'Metin Çıkarma' },
        { key: 'classify', label: 'Sınıflandırma' },
        { key: 'analyze', label: 'İçerik Analizi' },
        { key: 'legislation', label: 'Mevzuat Eşleştirme' },
        { key: 'summary', label: 'Özet' },
        { key: 'draft', label: 'Yazı Taslağı' },
        { key: 'routing', label: 'Birim Yönlendirme' },
        { key: 'reasoning', label: 'Muhakeme ve Doğrulama' },
    ],
    limits: {
        max_file_mb: 20,
        min_text_chars: 20,
        max_text_chars: 100000,
        allowed_extensions: ['.bmp', '.jpeg', '.jpg', '.md', '.pdf', '.png', '.tif', '.tiff', '.txt'],
    },
};

const ENTITY_LABELS = {
    tarih: 'Tarih', kurum: 'Kurum', kisi: 'Kişi', konu: 'Konu', referans_no: 'Referans No',
    adres: 'Adres', telefon: 'Telefon', eposta: 'E-posta',
};

const FIELD_LABELS = {
    'classification.document_type': 'Evrak türü',
    'draft.draft_type': 'Taslak türü',
    'routing.target_unit': 'Hedef birim',
    'routing.priority': 'Öncelik',
};

const PII_LABELS = {
    tc_kimlik: 'TC Kimlik No', iban: 'IBAN', telefon: 'Telefon', eposta: 'E-posta',
    sabit_tel: 'Sabit Telefon', plaka: 'Araç Plakası', pasaport: 'Pasaport No',
    vergi_no: 'Vergi No', sgk_no: 'SGK Sicil No', kredi_kart: 'Kredi Kartı', saglik_no: 'Sağlık Provizyon No',
    ehliyet: 'Ehliyet No',
};

export const SEVERITY = {
    correction: { label: 'Düzeltildi', icon: 'wrench', variant: 'warning' },
    warning: { label: 'Uyarı', icon: 'alert', variant: 'danger' },
    info: { label: 'Bilgi', icon: 'info', variant: 'primary' },
};

export const DRAFT_STATUS = {
    pending: { label: 'Onay bekliyor', variant: 'warning' },
    approved: { label: 'Onaylandı', variant: 'success' },
    edited: { label: 'Düzenlendi', variant: 'primary' },
    rejected: { label: 'Reddedildi', variant: 'danger' },
};

export const ROUTING_STATUS = {
    pending: { label: 'Onay bekliyor', variant: 'warning' },
    approved: { label: 'Onaylandı', variant: 'success' },
    changed: { label: 'Birim değiştirildi', variant: 'primary' },
};

function toMap(items) {
    return new Map((items || []).map((item) => [item.code, item]));
}

export class Vocabulary {
    constructor(meta = FALLBACK_META) {
        this.meta = { ...FALLBACK_META, ...meta, limits: { ...FALLBACK_META.limits, ...(meta?.limits || {}) } };
        this.documentTypes = toMap(this.meta.document_types);
        this.draftTypes = toMap(this.meta.draft_types);
        this.priorities = toMap(this.meta.priorities);
        this.units = this.meta.units || [];
        this.steps = this.meta.pipeline_steps?.length ? this.meta.pipeline_steps : FALLBACK_META.pipeline_steps;
        this.limits = this.meta.limits;
    }

    static humanize(code) {
        if (!code) return '—';
        const text = String(code).replace(/_/g, ' ');
        return text.charAt(0).toLocaleUpperCase('tr-TR') + text.slice(1);
    }

    documentType(code) { return this.documentTypes.get(code)?.label || Vocabulary.humanize(code); }
    draftType(code) { return this.draftTypes.get(code)?.label || Vocabulary.humanize(code); }
    priority(code) { return this.priorities.get(code)?.label || Vocabulary.humanize(code); }
    entity(code) { return ENTITY_LABELS[code] || Vocabulary.humanize(code); }

    priorityVariant(code) {
        return { acil: 'danger', yuksek: 'warning', normal: 'primary', dusuk: '' }[code] ?? '';
    }

    validationField(field) {
        if (FIELD_LABELS[field]) return FIELD_LABELS[field];
        const [group, name] = String(field).split('.');
        if (group === 'missing_fields') return `Eksik alan: ${Vocabulary.humanize(name)}`;
        if (group === 'pii') return `Kişisel veri: ${PII_LABELS[name] || name}`;
        if (group === 'draft_pii_leak') return `Taslakta kişisel veri: ${PII_LABELS[name] || name}`;
        return field;
    }

    /** Doğrulama kaydındaki ham değeri (kod) okunur etikete çevirir. */
    validationValue(field, value) {
        if (value == null) return null;
        if (field === 'classification.document_type') return this.documentType(value);
        if (field === 'draft.draft_type') return this.draftType(value);
        if (field === 'routing.priority') return this.priority(value);
        if (value === 'not_detected') return 'Tespit edilemedi';
        return value;
    }

    piiLabel(code) { return PII_LABELS[code] || code; }

    get acceptAttribute() { return this.limits.allowed_extensions.join(','); }

    get extensionsText() {
        return this.limits.allowed_extensions.map((ext) => ext.replace('.', '').toUpperCase()).join(', ');
    }
}

// ── Biçimlendiriciler ──

const numberFormat = new Intl.NumberFormat('tr-TR');
const dateFormat = new Intl.DateTimeFormat('tr-TR', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });

export const fmt = {
    percent: (ratio) => `%${Math.round((ratio || 0) * 100)}`,
    number: (value) => numberFormat.format(value || 0),
    seconds(value) {
        const s = Number(value) || 0;
        if (s < 60) return `${s.toLocaleString('tr-TR', { maximumFractionDigits: 1 })} sn`;
        return `${Math.floor(s / 60)} dk ${String(Math.round(s % 60)).padStart(2, '0')} sn`;
    },
    relativeTime(isoString) {
        if (!isoString) return '—';
        const diff = Date.now() - new Date(isoString).getTime();
        const mins = Math.round(diff / 60000);
        if (mins < 1) return 'az önce';
        if (mins < 60) return `${mins} dk önce`;
        const hours = Math.round(mins / 60);
        if (hours < 24) return `${hours} saat önce`;
        const days = Math.round(hours / 24);
        if (days < 30) return `${days} gün önce`;
        return this.date(isoString);
    },
    date(iso) {
        if (!iso) return '—';
        const date = new Date(iso);
        return Number.isNaN(date.getTime()) ? iso : dateFormat.format(date);
    },
    fileSize(bytes) {
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toLocaleString('tr-TR', { maximumFractionDigits: 0 })} KB`;
        return `${(bytes / 1024 / 1024).toLocaleString('tr-TR', { maximumFractionDigits: 1 })} MB`;
    },
};
