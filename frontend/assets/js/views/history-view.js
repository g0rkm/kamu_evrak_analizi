import { debounce, h, icon, replace } from '../core/dom.js';
import { confirmDialog } from '../core/ui.js';
import { DRAFT_STATUS, fmt } from '../core/vocabulary.js';

const PAGE_SIZE = 25;

export class HistoryView {
    title = 'Geçmiş';

    constructor({ api, vocab, toaster, navigate }) {
        this.api = api;
        this.vocab = vocab;
        this.toaster = toaster;
        this.navigate = navigate;
        this.items = [];
        this.total = 0;
        this.hasMore = false;
        this.element = this.build();
    }

    build() {
        this.statsRoot = h('div', { style: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '18px' } });
        this.tableRoot = h('div', { style: { overflowX: 'auto' } });
        this.moreRoot = h('div', { style: { textAlign: 'center', fontSize: '13px', color: 'var(--color-neutral-700)', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '10px' } });

        this.search = h('input', {
            class: 'input', type: 'search', id: 'historySearch',
            placeholder: 'Başlık, kişi veya konu yazın…',
            onInput: debounce(() => this.load(), 300),
        });
        this.typeFilter = h('select', { class: 'input', id: 'historyType', onChange: () => this.load() },
            h('option', { value: '' }, 'Tümü'),
            [...this.vocab.documentTypes.values()].map((t) => h('option', { value: t.code }, t.label)));
        this.statusFilter = h('select', { class: 'input', id: 'historyStatus', onChange: () => this.load() },
            h('option', { value: '' }, 'Tümü'),
            h('option', { value: 'pending' }, 'Onay bekliyor'),
            h('option', { value: 'approved' }, 'Onaylandı'),
            h('option', { value: 'edited' }, 'Düzenlendi'),
            h('option', { value: 'rejected' }, 'Reddedildi'));
        this.sortSelect = h('select', { class: 'input', id: 'historySort', onChange: () => this.load() },
            h('option', { value: 'newest' }, 'En yeni önce'),
            h('option', { value: 'oldest' }, 'En eski önce'),
            h('option', { value: 'confidence_desc' }, 'Eminlik (yüksek → düşük)'),
            h('option', { value: 'confidence_asc' }, 'Eminlik (düşük → yüksek)'));
        this.dateFromInput = h('input', { class: 'input', type: 'date', id: 'historyFrom', onChange: () => this.load() });
        this.dateToInput = h('input', { class: 'input', type: 'date', id: 'historyTo', onChange: () => this.load() });
        this.favoriteCheckbox = h('input', { type: 'checkbox', onChange: () => this.load() });

        return h('section', { style: { display: 'flex', flexDirection: 'column', gap: '28px' } },
            h('div', { class: 'page-bar' },
                h('div', null,
                    h('h1', { style: { margin: 0, fontWeight: 400 } }, 'Geçmiş evraklar'),
                    h('p', { style: { margin: '4px 0 0', color: 'var(--color-neutral-700)' } }, 'Daha önce incelenen evrakları bulun, açın ve onay durumlarını takip edin.')),
                h('div', { style: { display: 'flex', gap: '8px', flexWrap: 'wrap' } },
                    h('button', { type: 'button', class: 'btn btn-secondary', onClick: () => this.exportCsv() }, 'Excel olarak indir'),
                    h('button', { type: 'button', class: 'btn btn-secondary', onClick: () => this.navigate('#export') }, 'Diğer aktarım seçenekleri'))),
            this.statsRoot,
            h('div', { class: 'card', style: { padding: '24px', gap: '18px' } },
                h('div', { class: 'split', style: { display: 'grid', gridTemplateColumns: 'minmax(220px, 2fr) repeat(3, minmax(140px, 1fr))', gap: '12px' } },
                    h('div', { class: 'field' }, h('label', { for: 'historySearch' }, 'Ara'), this.search),
                    h('div', { class: 'field' }, h('label', { for: 'historyType' }, 'Evrak türü'), this.typeFilter),
                    h('div', { class: 'field' }, h('label', { for: 'historyStatus' }, 'Durum'), this.statusFilter),
                    h('div', { class: 'field' }, h('label', { for: 'historySort' }, 'Sıralama'), this.sortSelect)),
                h('div', { style: { display: 'flex', gap: '12px', alignItems: 'flex-end', flexWrap: 'wrap' } },
                    h('div', { class: 'field', style: { width: '180px' } }, h('label', { for: 'historyFrom' }, 'Başlangıç tarihi'), this.dateFromInput),
                    h('div', { class: 'field', style: { width: '180px' } }, h('label', { for: 'historyTo' }, 'Bitiş tarihi'), this.dateToInput),
                    h('label', { class: 'radio', style: { marginLeft: '4px', paddingBottom: '8px' } },
                        this.favoriteCheckbox,
                        h('span', { class: 'dot', style: { borderRadius: '3px' } }),
                        'Yalnızca favoriler')),
                this.tableRoot,
                this.moreRoot));
    }

    async show() {
        await this.refresh();
    }

    async refresh() {
        await Promise.all([this.loadStats(), this.load()]);
    }

    async loadStats() {
        try {
            const stats = await this.api.historyStats();
            this.renderStats(stats);
        } catch (error) {
            replace(this.statsRoot, h('div', { class: 'alert alert--danger', style: { gridColumn: '1 / -1' } }, icon('alert'), `İstatistikler yüklenemedi: ${error.message}`));
        }
    }

    renderStats(stats) {
        const reviewed = (stats.by_draft_status?.approved || 0) + (stats.by_draft_status?.edited || 0);
        const pending = stats.by_draft_status?.pending ?? Math.max(0, (stats.total || 0) - reviewed);
        const avgConf = stats.avg_confidence || 0;
        const confHint = avgConf >= 0.8 ? 'Yüksek düzey' : avgConf >= 0.5 ? 'Orta düzey' : 'Kontrol önerilir';
        const cards = [
            ['Toplam evrak', fmt.number(stats.total), 'Bugüne kadar incelenen'],
            ['Ortalama eminlik', fmt.percent(avgConf), confHint],
            ['Onaylanan taslak', fmt.number(reviewed), `${pending} taslak onay bekliyor`],
        ];
        replace(this.statsRoot, ...cards.map(([label, value, hint]) => h('div', {
            class: 'card', style: { padding: '20px', textAlign: 'center', alignItems: 'center', gap: '4px' },
        },
            h('div', { class: 'card-kicker' }, label),
            h('div', { style: { fontFamily: 'var(--font-heading)', fontSize: '38px', lineHeight: 1.1, fontVariantNumeric: 'tabular-nums' } }, value),
            h('div', { style: { fontSize: '12px', color: 'var(--color-neutral-700)' } }, hint))));
    }

    async load({ append = false } = {}) {
        const query = {
            q: this.search.value.trim(),
            documentType: this.typeFilter.value,
            draftStatus: this.statusFilter.value,
            sort: this.sortSelect.value,
            limit: PAGE_SIZE,
            offset: append ? this.items.length : 0,
            dateFrom: this.dateFromInput?.value || undefined,
            dateTo: this.dateToInput?.value || undefined,
            favorite: this.favoriteCheckbox?.checked ? true : undefined,
        };
        if (!append) replace(this.tableRoot, h('div', { class: 'loading-line' }, 'Yükleniyor…'));
        try {
            const page = await this.api.history(query);
            this.items = append ? [...this.items, ...page.items] : page.items;
            this.total = page.total;
            this.hasMore = page.has_more === true;
            this.renderTable();
        } catch (error) {
            replace(this.tableRoot, h('div', { class: 'alert alert--danger' }, icon('alert'), `Geçmiş yüklenemedi: ${error.message}`));
        }
    }

    renderTable() {
        const filtered = this.search.value.trim() || this.typeFilter.value || this.statusFilter.value || this.dateFromInput?.value || this.dateToInput?.value || this.favoriteCheckbox?.checked;
        const sort = this.sortSelect?.value || 'newest';
        if (sort === 'oldest') this.items.sort((a, b) => a.timestamp.localeCompare(b.timestamp));
        else if (sort === 'confidence_desc') this.items.sort((a, b) => b.confidence_score - a.confidence_score);
        else if (sort === 'confidence_asc') this.items.sort((a, b) => a.confidence_score - b.confidence_score);
        else this.items.sort((a, b) => b.timestamp.localeCompare(a.timestamp));

        if (!this.items.length) {
            replace(this.tableRoot, h('div', { class: 'empty empty--compact' },
                h('h3', null, filtered ? 'Sonuç bulunamadı' : 'Henüz evrak incelenmedi'),
                h('p', null, filtered ? 'Arama ölçütlerini değiştirip tekrar deneyin.' : 'İlk evrakınızı analiz ettiğinizde burada listelenecek.')));
            replace(this.moreRoot);
            return;
        }

        const rows = this.items.map((item) => {
            const status = DRAFT_STATUS[item.draft_status] || DRAFT_STATUS.pending;
            const open = () => this.navigate(`#/analiz/${encodeURIComponent(item.id)}`);
            return h('tr', { class: 'is-clickable', tabindex: 0, onClick: open, onKeydown: (e) => { if (e.key === 'Enter') open(); } },
                h('td', { style: { whiteSpace: 'nowrap', color: 'var(--color-neutral-700)', verticalAlign: 'top', paddingTop: '14px' }, title: fmt.date(item.timestamp) }, fmt.relativeTime(item.timestamp)),
                h('td', { style: { padding: '12px 9px' } },
                    h('div', { style: { fontSize: '15px', overflowWrap: 'anywhere' } }, item.source_name || 'Adsız evrak'),
                    item.summary ? h('div', { style: { fontSize: '12px', color: 'var(--color-neutral-700)', maxWidth: '420px' } }, item.summary) : null),
                h('td', { style: { verticalAlign: 'top', paddingTop: '14px' } }, h('span', { class: 'tag tag-neutral' }, this.vocab.documentType(item.document_type))),
                h('td', { style: { verticalAlign: 'top', paddingTop: '14px', fontVariantNumeric: 'tabular-nums' } }, fmt.percent(item.confidence_score)),
                h('td', { style: { verticalAlign: 'top', paddingTop: '14px' } }, h('span', { class: 'tag tag-accent', style: { whiteSpace: 'nowrap' } }, status.label)),
                h('td', { style: { verticalAlign: 'top', paddingTop: '8px', textAlign: 'right', whiteSpace: 'nowrap' } },
                    h('button', { type: 'button', class: 'btn btn-ghost', onClick: (e) => { e.stopPropagation(); open(); } }, 'Aç'),
                    h('button', { type: 'button', class: 'btn btn-ghost', style: { color: 'var(--color-neutral-700)' }, onClick: (e) => { e.stopPropagation(); this.remove(item); } }, 'Sil')));
        });

        replace(this.tableRoot, h('table', { class: 'table' },
            h('thead', null, h('tr', null,
                h('th', null, 'Tarih'),
                h('th', null, 'Evrak'),
                h('th', null, 'Tür'),
                h('th', null, 'Eminlik'),
                h('th', null, 'Durum'),
                h('th', { style: { textAlign: 'right' } }, 'İşlem'))),
            h('tbody', null, rows)));

        replace(this.moreRoot,
            h('div', null, `${fmt.number(this.total)} kayıttan ${fmt.number(this.items.length)} tanesi gösteriliyor`),
            this.hasMore
                ? h('button', { type: 'button', class: 'btn btn-secondary', onClick: () => this.load({ append: true }) }, 'Daha fazla yükle')
                : null);
    }

    async remove(item) {
        const ok = await confirmDialog({
            title: 'Evrak kaydı silinsin mi?',
            message: `"${item.source_name || 'Adsız evrak'}" kaydı ve memur kararları kalıcı olarak silinecek.`,
            confirmText: 'Sil',
            danger: true,
        });
        if (!ok) return;
        try {
            await this.api.deleteRecord(item.id);
            this.toaster.success('Kayıt silindi.');
            await this.refresh();
        } catch (error) {
            this.toaster.error(`Kayıt silinemedi: ${error.message}`);
        }
    }

    async exportCsv() {
        try {
            const resp = await fetch('/api/history/export-csv');
            if (!resp.ok) throw new Error('Tablo indirilemedi.');
            const blob = await resp.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `gecmis_${new Date().toISOString().slice(0, 10)}.csv`;
            a.click();
            URL.revokeObjectURL(url);
            this.toaster.success('Excel tablosu indirildi.');
        } catch (error) {
            this.toaster.error(`İndirme başarısız: ${error.message}`);
        }
    }
}
