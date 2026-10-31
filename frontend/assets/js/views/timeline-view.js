import { ApiClient } from '../core/api.js';
import { h, replace } from '../core/dom.js';
import { DRAFT_STATUS, Vocabulary } from '../core/vocabulary.js';

const dayFmt = new Intl.DateTimeFormat('tr-TR', { day: 'numeric', month: 'long', year: 'numeric', weekday: 'long' });
const timeFmt = new Intl.DateTimeFormat('tr-TR', { hour: '2-digit', minute: '2-digit' });

export class TimelineView {
    title = 'Zaman çizelgesi';

    constructor(container) {
        this._container = container;
        this._api = new ApiClient();
    }

    async render(root = this._container) {
        this.startEl = h('input', { class: 'input', type: 'date', id: 'timelineStart' });
        this.endEl = h('input', { class: 'input', type: 'date', id: 'timelineEnd' });
        this.content = h('div', { id: 'timelineContent', style: { display: 'flex', flexDirection: 'column', gap: '20px' } });

        const section = h('section', { style: { display: 'flex', flexDirection: 'column', gap: '26px', maxWidth: '820px', margin: '0 auto' } },
            h('div', { style: { textAlign: 'center' } },
                h('h1', { style: { margin: 0, fontWeight: 400 } }, 'Zaman çizelgesi'),
                h('p', { style: { margin: '6px 0 0', color: 'var(--color-neutral-700)' } }, 'Evrakların hangi gün işlendiğini sırasıyla görün.')),
            h('div', { style: { display: 'flex', gap: '12px', justifyContent: 'center', alignItems: 'flex-end', flexWrap: 'wrap' } },
                h('div', { class: 'field', style: { width: '180px' } }, h('label', { for: 'timelineStart' }, 'Başlangıç'), this.startEl),
                h('div', { class: 'field', style: { width: '180px' } }, h('label', { for: 'timelineEnd' }, 'Bitiş'), this.endEl),
                h('button', { type: 'button', class: 'btn btn-primary', id: 'timelineLoadBtn', onClick: () => this._loadTimeline() }, 'Göster')),
            this.content);

        replace(root, section);
        await this._loadTimeline();
    }

    async _loadTimeline() {
        let url = '/history/timeline';
        const params = [];
        if (this.startEl?.value) params.push('start_date=' + encodeURIComponent(this.startEl.value));
        if (this.endEl?.value) params.push('end_date=' + encodeURIComponent(this.endEl.value));
        if (params.length) url += '?' + params.join('&');
        replace(this.content, h('div', { class: 'loading-line' }, 'Yükleniyor…'));
        try {
            const [data, meta] = await Promise.all([
                this._api.request(url),
                this._api.meta().catch(() => null),
            ]);
            const vocab = new Vocabulary(meta || undefined);
            this._renderTimeline(data.timeline || data.records || [], vocab);
        } catch {
            replace(this.content, h('p', { class: 'error-text', style: { textAlign: 'center' } }, 'Zaman çizelgesi yüklenemedi.'));
        }
    }

    _renderTimeline(items, vocab) {
        if (!items.length) {
            replace(this.content,
                h('div', { style: { textAlign: 'center', padding: '40px 0', color: 'var(--color-neutral-700)', fontSize: '14px' } }, 'Bu aralıkta kayıt bulunamadı.'));
            return;
        }
        const sorted = [...items].sort((a, b) => String(b.timestamp || b.date || '').localeCompare(String(a.timestamp || a.date || '')));
        const groups = new Map();
        for (const item of sorted) {
            const d = new Date(item.timestamp || item.date || '');
            const valid = !Number.isNaN(d.getTime());
            const dayKey = valid ? dayFmt.format(d) : (item.date || 'Tarihsiz');
            const time = valid ? timeFmt.format(d) : '—';
            if (!groups.has(dayKey)) groups.set(dayKey, []);
            groups.get(dayKey).push({ item, time });
        }

        replace(this.content, ...[...groups.entries()].map(([dayLabel, list]) => h('div', { style: { display: 'flex', flexDirection: 'column' } },
            h('div', { style: { fontFamily: 'var(--font-heading)', fontSize: '20px', borderBottom: '1px solid var(--color-divider)', paddingBottom: '6px', marginBottom: '6px' } }, dayLabel),
            ...list.map(({ item, time }) => {
                const conf = Math.round((item.confidence_score || 0) * 100);
                const status = DRAFT_STATUS[item.draft_status] || DRAFT_STATUS.pending;
                const row = h('div', { style: { display: 'grid', gridTemplateColumns: '70px 18px 1fr', gap: '14px', padding: '14px 0' } },
                    h('span', { style: { fontSize: '14px', color: 'var(--color-neutral-700)', textAlign: 'right', fontVariantNumeric: 'tabular-nums' } }, time),
                    h('span', { style: { display: 'flex', justifyContent: 'center', paddingTop: '6px' } },
                        h('span', { style: { width: '9px', height: '9px', borderRadius: '50%', border: '1.5px solid var(--color-accent)' } })),
                    h('div', { style: { display: 'flex', flexDirection: 'column', gap: '4px' } },
                        h('span', { style: { fontSize: '16px' } }, item.source_name || item.file_name || 'Adsız evrak'),
                        h('span', { style: { fontSize: '13px', color: 'var(--color-neutral-700)' } },
                            `${vocab.documentType(item.document_type)} · Eminlik %${conf} · ${status.label}`)));
                return item.id
                    ? h('a', { href: `#/analiz/${encodeURIComponent(item.id)}`, style: { textDecoration: 'none', color: 'var(--color-text)' } }, row)
                    : row;
            }))));
    }
}
