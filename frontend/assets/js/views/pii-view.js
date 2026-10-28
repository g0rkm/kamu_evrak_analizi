import { ApiClient } from '../core/api.js';
import { h, replace } from '../core/dom.js';
import { Vocabulary } from '../core/vocabulary.js';

const DEFAULT_SAMPLE = 'Başvuru sahibi Ayşe Kaya (T.C. 12345678901), 0532 123 45 67 numaralı telefondan ulaşılabilir. Adres: Çankaya, Ankara.';

export class PiiView {
    title = 'Kişisel bilgi kontrolü';

    constructor(container) {
        this._container = container;
        this._api = new ApiClient();
        this._vocab = new Vocabulary();
    }

    async render(root = this._container) {
        this.textarea = h('textarea', {
            class: 'input', id: 'piiInputText',
            placeholder: 'Kontrol edilecek metni buraya yapıştırın…',
            value: DEFAULT_SAMPLE,
            style: { minHeight: '170px', fontSize: '15px' },
        });
        this.resultsRoot = h('div', { id: 'piiResults' });

        const actionBtn = (cls, id, title, hint, fn) => h('button', {
            type: 'button', id, class: `btn ${cls}`,
            style: { flexDirection: 'column', padding: '16px', gap: '4px' },
            onClick: fn,
        },
            h('span', { style: { fontSize: '16px' } }, title),
            h('span', { style: { fontFamily: 'var(--font-body)', fontWeight: 400, fontSize: '12px', color: 'var(--color-neutral-700)' } }, hint));

        const section = h('section', { style: { display: 'flex', flexDirection: 'column', gap: '26px', maxWidth: '860px', margin: '0 auto' } },
            h('div', { style: { textAlign: 'center' } },
                h('h1', { style: { margin: 0, fontWeight: 400 } }, 'Kişisel bilgi kontrolü'),
                h('p', { style: { margin: '6px auto 0', color: 'var(--color-neutral-700)', maxWidth: '600px', textWrap: 'pretty' } },
                    'Bir metni paylaşmadan önce içindeki T.C. kimlik no, telefon, adres gibi kişisel bilgileri bulun ve gizleyin (KVKK).')),
            this.textarea,
            h('div', { class: 'split', style: { display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: '14px' } },
                actionBtn('btn-secondary', 'piiAnalyzeBtn', 'Bul ve göster', 'Metni değiştirmez', () => this._run('find')),
                actionBtn('btn-primary', 'piiMaskBtn', 'Gizle (maskele)', 'Örn. 123******78', () => this._run('mask')),
                actionBtn('btn-secondary', 'piiRedactBtn', 'Tamamen kaldır', 'Yerine [GİZLİ] yazar', () => this._run('redact'))),
            this.resultsRoot);

        replace(root, section);
    }

    async _run(mode) {
        const text = this.textarea?.value?.trim();
        if (!text) return;
        try {
            const [analysis, masked] = await Promise.all([
                this._api.request('/pii/analyze', { method: 'POST', json: { text } }).catch(() => null),
                this._api.request('/mask-pii', { method: 'POST', json: { text } }),
            ]);
            const types = analysis?.pii_types || {};
            const total = masked?.pii_count ?? Object.values(types).reduce((a, b) => a + b, 0);
            const title = mode === 'mask' ? 'Maskelenmiş metin' : mode === 'redact' ? 'Bilgileri kaldırılmış metin' : 'Bulunan kişisel bilgiler';
            const output = mode === 'mask'
                ? (masked.masked_text || text)
                : mode === 'redact'
                    ? (masked.masked_text || text).replace(/\[\*\*\*[A-Z_]+\*\*\*\]|\*{3,}/g, '[GİZLİ]')
                    : text;

            const tags = Object.entries(types).map(([k, v]) => h('span', { class: 'tag tag-accent' }, `${this._vocab.piiLabel(k)} · ${v}`));
            replace(this.resultsRoot, h('div', { class: 'card', style: { padding: '22px', gap: '14px' } },
                h('div', { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: '12px', flexWrap: 'wrap' } },
                    h('div', { class: 'card-kicker' }, title),
                    h('span', { style: { fontSize: '13px', color: 'var(--color-neutral-700)' } }, `${total} kişisel bilgi bulundu`)),
                tags.length ? h('div', { style: { display: 'flex', gap: '8px', flexWrap: 'wrap' } }, ...tags) : null,
                h('div', { style: { fontSize: '15px', lineHeight: 1.7, borderTop: '1px solid var(--color-divider)', paddingTop: '14px', whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' } }, output)));
        } catch {
            replace(this.resultsRoot, h('div', { class: 'card', style: { padding: '22px' } },
                h('p', { class: 'error-text', style: { margin: 0 } }, 'Kişisel bilgi kontrolü yapılamadı.')));
        }
    }
}
