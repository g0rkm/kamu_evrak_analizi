import { ApiClient } from '../core/api.js';
import { h, replace } from '../core/dom.js';
import { DRAFT_STATUS, Vocabulary, fmt } from '../core/vocabulary.js';

const SUGGESTIONS = ['imar planı', 'bilgi edinme', 'dilekçe', 'kaldırım'];

export class SearchView {
    title = 'Arama';

    constructor(container) {
        this._container = container;
        this._api = new ApiClient();
    }

    async render(root = this._container) {
        this.input = h('input', {
            class: 'input', type: 'search', id: 'searchQuery',
            placeholder: 'Örneğin: imar planı, Ayşe Kaya, Ankara Valiliği',
            style: { flex: 1, minWidth: '240px', minHeight: '46px', fontSize: '16px' },
        });
        this.priority = h('select', { class: 'input', id: 'searchPriority', style: { width: '170px', minHeight: '46px' }, onChange: () => this.input.value.trim() && this._doSearch() },
            h('option', { value: '' }, 'Tüm öncelikler'),
            h('option', { value: 'acil' }, 'Acil'),
            h('option', { value: 'yuksek' }, 'Yüksek'),
            h('option', { value: 'normal' }, 'Normal'),
            h('option', { value: 'dusuk' }, 'Düşük'));
        this.resultsRoot = h('div', { id: 'searchResults', style: { width: '100%', maxWidth: '720px', marginTop: '10px' } },
            h('div', { style: { textAlign: 'center', color: 'var(--color-neutral-700)', fontSize: '14px', padding: '30px 0', borderTop: '1px solid var(--color-divider)' } },
                'Sonuçlar burada listelenecek.'));

        const form = h('form', {
            id: 'searchForm', style: { display: 'flex', gap: '10px', width: '100%', maxWidth: '720px', flexWrap: 'wrap' },
            onSubmit: (e) => { e.preventDefault(); this._doSearch(); },
        }, this.input, this.priority, h('button', { type: 'submit', class: 'btn btn-primary', style: { minHeight: '46px', padding: '0 26px', fontSize: '16px' } }, 'Ara'));

        const section = h('section', { style: { display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '22px', paddingTop: '24px' } },
            h('h1', { style: { margin: 0, fontWeight: 400 } }, 'Evraklarda arama'),
            h('p', { style: { margin: '-10px 0 0', color: 'var(--color-neutral-700)', textAlign: 'center' } }, 'Bir kelime, kişi adı, kurum veya konu yazın.'),
            form,
            h('div', { style: { display: 'flex', gap: '8px', flexWrap: 'wrap', justifyContent: 'center', fontSize: '13px', color: 'var(--color-neutral-700)', alignItems: 'center' } },
                'Sık arananlar:',
                ...SUGGESTIONS.map((label) => h('button', {
                    type: 'button', class: 'btn btn-secondary', style: { fontSize: '13px', padding: '4px 12px' },
                    onClick: () => { this.input.value = label; this._doSearch(); },
                }, label))),
            this.resultsRoot);

        replace(root, section);
    }

    async _doSearch() {
        const query = this.input.value.trim();
        const priority = this.priority.value;
        if (!query) return;
        replace(this.resultsRoot, h('div', { class: 'loading-line' }, 'Aranıyor…'));
        try {
            const [resp, meta] = await Promise.all([
                this._api.fullTextSearch(query),
                this._api.meta().catch(() => null),
            ]);
            const vocab = new Vocabulary(meta || undefined);
            let results = resp.results || [];
            if (priority) {
                const map = { acil: ['acil', 'urgent'], yuksek: ['yuksek', 'high'], normal: ['normal'], dusuk: ['dusuk', 'low'] };
                const allowed = map[priority] || [priority];
                results = results.filter((r) => allowed.includes(r.priority));
            }
            const countLine = h('div', { style: { fontSize: '13px', color: 'var(--color-neutral-700)', borderBottom: '1px solid var(--color-divider)', paddingBottom: '8px' } },
                `"${query}" için ${results.length} sonuç bulundu`);
            if (!results.length) {
                replace(this.resultsRoot, countLine,
                    h('div', { style: { textAlign: 'center', color: 'var(--color-neutral-700)', fontSize: '14px', padding: '30px 0' } }, 'Eşleşen evrak bulunamadı.'));
                return;
            }
            replace(this.resultsRoot, countLine, ...results.map((r) => {
                const status = DRAFT_STATUS[r.draft_status] || DRAFT_STATUS.pending;
                return h('a', {
                    href: `#/analiz/${encodeURIComponent(r.id)}`,
                    style: { padding: '16px 0', borderBottom: '1px solid var(--color-divider)', display: 'flex', flexDirection: 'column', gap: '4px', textDecoration: 'none', color: 'var(--color-text)' },
                },
                    h('div', { style: { fontFamily: 'var(--font-heading)', fontSize: '20px' } }, r.source_name || r.id || 'Evrak'),
                    r.summary ? h('div', { style: { fontSize: '14px' } }, r.summary) : null,
                    h('div', { style: { fontSize: '12px', color: 'var(--color-neutral-700)' } },
                        `${vocab.documentType(r.document_type)} · ${fmt.relativeTime(r.timestamp || r.created_at)} · ${status.label}`));
            }));
        } catch {
            replace(this.resultsRoot, h('p', { class: 'error-text', style: { textAlign: 'center' } }, 'Arama yapılamadı.'));
        }
    }
}
