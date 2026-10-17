import { badge, debounce, emptyState, h, icon, meter, replace } from '../core/dom.js';
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
        this.statsRoot = h('div', { class: 'grid-4' });
        this.distributionRoot = h('div');
        this.tableRoot = h('div');
        this.moreRoot = h('div', { class: 'row', style: { justifyContent: 'center' } });

        this.search = h('input', { class: 'input', type: 'search', id: 'historySearch', placeholder: 'Özet, başlık, tür veya anahtar kelimede ara…', 'aria-label': 'Arama',
            onInput: debounce(() => this.load(), 300) });
        this.typeFilter = h('select', { class: 'select', 'aria-label': 'Evrak türüne göre filtrele', onChange: () => this.load() },
            h('option', { value: '' }, 'Tüm evrak türleri'),
            [...this.vocab.documentTypes.values()].map((t) => h('option', { value: t.code }, t.label)));
        this.statusFilter = h('select', { class: 'select', 'aria-label': 'Taslak durumuna göre filtrele', onChange: () => this.load() },
            h('option', { value: '' }, 'Tüm durumlar'),
            h('option', { value: 'pending' }, 'Bekliyor'),
            h('option', { value: 'approved' }, 'Onaylandı'),
            h('option', { value: 'rejected' }, 'Reddedildi'),
            h('option', { value: 'edited' }, 'Düzenlendi'));
        this.sortSelect = h('select', { class: 'select', 'aria-label': 'Sıralama', onChange: () => this.load() },
            h('option', { value: 'newest' }, 'En yeni önce'),
            h('option', { value: 'oldest' }, 'En eski önce'),
            h('option', { value: 'confidence_desc' }, 'Güven (yüksek → düşük)'),
            h('option', { value: 'confidence_asc' }, 'Güven (düşük → yüksek)'));
        this.dateFromInput = h('input', { type: 'date', class: 'input input--sm', 'aria-label': 'Başlangıç tarihi', onChange: () => this.load() });
        this.dateToInput = h('input', { type: 'date', class: 'input input--sm', 'aria-label': 'Bitiş tarihi', onChange: () => this.load() });

        return h('div', { class: 'stack' },
            h('div', { class: 'view-header' },
                h('div', null, h('h1', null, 'Analiz geçmişi'), h('p', null, 'Önceki analizleri arayın, açın ve memur kararlarını takip edin.')),
                h('button', { type: 'button', class: 'btn btn--ghost btn--sm', onClick: () => this.exportAll() }, icon('download'), 'Tümünü dışa aktar'),
                h('button', { type: 'button', class: 'btn btn--ghost btn--sm', onClick: () => this.exportCsv() }, icon('download'), 'CSV indir'),
                h('button', { type: 'button', class: 'btn btn--danger-ghost btn--sm', onClick: () => this.clearAll() }, icon('trash'), 'Tümünü sil'),
                h('button', { type: 'button', class: 'btn btn--ghost btn--sm', onClick: () => this.importRecords() }, icon('upload'), 'İçe aktar'),
                h('button', { type: 'button', class: 'btn btn--secondary', onClick: () => this.refresh() }, icon('refresh'), 'Yenile')),
            this.statsRoot,
            h('section', { class: 'card' },
                h('div', { class: 'card__header' }, h('h2', { class: 'card__title' }, icon('chart'), 'Evrak türü dağılımı')),
                h('div', { class: 'card__body' }, this.distributionRoot)),
            h('section', { class: 'card' },
                h('div', { class: 'card__header' }, h('h2', { class: 'card__title' }, icon('history'), 'Kayıtlar')),
                h('div', { class: 'card__body stack' },
                    h('div', { class: 'toolbar' },
                        h('label', { class: 'input-icon' }, h('span', { class: 'sr-only' }, 'Geçmişte ara'), icon('search'), this.search),
                        this.typeFilter,
                        this.statusFilter,
                        this.sortSelect,
                        h('span', { class: 'small muted' }, 'Tarih:'),
                        this.dateFromInput,
                        this.dateToInput),
                    this.tableRoot,
                    this.moreRoot)),
        );
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
        const tile = (iconName, label, value, title = '') => h('div', { class: 'stat', title }, h('div', { class: 'stat__label' }, icon(iconName), label), h('div', { class: 'stat__value' }, value));
        replace(this.statsRoot,
            tile('file', 'Toplam analiz', fmt.number(stats.total), `${stats.total} analiz kaydı`),
            tile('shieldCheck', 'Ortalama güven', fmt.percent(stats.avg_confidence), `Ort: %${Math.round(stats.avg_confidence * 100)} · Min: %${Math.round((stats.min_confidence || 0) * 100)} · Maks: %${Math.round((stats.max_confidence || 0) * 100)}`),
            tile('clock', 'Ortalama süre', fmt.seconds(stats.avg_processing_time), `Ort: ${stats.avg_processing_time.toFixed(1)}s · Min: ${(stats.min_processing_time || 0).toFixed(1)}s · Maks: ${(stats.max_processing_time || 0).toFixed(1)}s`),
            tile('userCheck', 'Onaylanan taslak', fmt.number(reviewed), `Onaylanmış: ${stats.by_draft_status?.approved || 0}, Düzenlenmiş: ${stats.by_draft_status?.edited || 0}`));

        const entries = Object.entries(stats.by_type || {}).sort((a, b) => b[1] - a[1]);
        if (!entries.length) {
            replace(this.distributionRoot, h('p', { class: 'muted' }, 'Henüz veri yok.'));
            return;
        }
        const max = entries[0][1];
        replace(this.distributionRoot, entries.slice(0, 10).map(([code, count]) => h('div', { class: 'bar-row' },
            h('span', null, this.vocab.documentType(code)),
            meter(count / max),
            h('span', { class: 'bar-row__value' }, `${count} · ${fmt.percent(count / stats.total)}`))));
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
        };
        if (!append) replace(this.tableRoot, emptyState({ iconName: 'loader', title: 'Yükleniyor…', compact: true }));
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
        const filtered = this.search.value.trim() || this.typeFilter.value || this.statusFilter.value || this.dateFromInput?.value || this.dateToInput?.value;
        const sort = this.sortSelect?.value || 'newest';
        if (sort === 'oldest') this.items.sort((a, b) => a.timestamp.localeCompare(b.timestamp));
        else if (sort === 'confidence_desc') this.items.sort((a, b) => b.confidence_score - a.confidence_score);
        else if (sort === 'confidence_asc') this.items.sort((a, b) => a.confidence_score - b.confidence_score);
        else this.items.sort((a, b) => b.timestamp.localeCompare(a.timestamp));

        if (!this.items.length) {
            replace(this.tableRoot, filtered
                ? emptyState({ iconName: 'search', title: 'Sonuç bulunamadı', text: 'Arama ölçütlerini değiştirip tekrar deneyin.', compact: true })
                : emptyState({ iconName: 'history', title: 'Henüz analiz yapılmadı', text: 'İlk analizinizi yaptığınızda burada listelenecek.', compact: true,
                    action: h('a', { class: 'btn btn--primary', href: '#/analiz' }, icon('sparkles'), 'Analiz başlat') }));
            replace(this.moreRoot);
            return;
        }

        const rows = this.items.map((item) => {
            const status = DRAFT_STATUS[item.draft_status] || DRAFT_STATUS.pending;
            const open = () => this.navigate(`#/analiz/${item.id}`);
            const remove = h('button', {
                type: 'button', class: 'btn btn--danger-ghost btn--icon btn--sm', 'aria-label': 'Kaydı sil', title: 'Sil',
                onClick: (e) => { e.stopPropagation(); this.remove(item); },
            }, icon('trash'));
            return h('tr', { class: 'is-clickable', tabindex: 0, onClick: open, onKeydown: (e) => { if (e.key === 'Enter') open(); } },
                h('td', { class: 'small muted', style: { whiteSpace: 'nowrap' }, 'data-optional': true, title: fmt.date(item.timestamp) }, fmt.relativeTime(item.timestamp)),
                h('td', null,
                    h('div', { style: { fontWeight: 600, overflowWrap: 'anywhere' } }, item.source_name || 'Adsız analiz'),
                    item.summary ? h('div', { class: 'small muted', style: { maxWidth: '520px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }, item.summary) : null),
                h('td', null, badge(this.vocab.documentType(item.document_type), 'primary')),
                h('td', { style: { minWidth: '90px' }, 'data-optional': true }, h('div', { class: 'small' }, fmt.percent(item.confidence_score)), meter(item.confidence_score)),
                h('td', null, badge(status.label, status.variant), item.status === 'partial' ? badge('Kısmi', 'warning') : null),
                h('td', { class: 'small muted', 'data-optional': true }, fmt.seconds(item.processing_time)),
                h('td', null, remove));
        });

        const headers = [['Tarih', true], ['Evrak'], ['Tür'], ['Güven', true], ['Taslak'], ['Süre', true], ['']];
        replace(this.tableRoot, h('div', { class: 'table-wrap' }, h('table', { class: 'table' },
            h('thead', null, h('tr', null, headers.map(([t, optional]) => h('th', { scope: 'col', 'data-optional': optional || null }, t)))),
            h('tbody', null, rows))));

        replace(this.moreRoot,
            h('span', { class: 'small muted' }, `${fmt.number(this.total)} kayıttan ${fmt.number(this.items.length)} tanesi gösteriliyor`,
                this.total > PAGE_SIZE ? ` · Sayfa ${Math.ceil(this.items.length / PAGE_SIZE)}/${Math.ceil(this.total / PAGE_SIZE)}` : ''),
            this.hasMore
                ? h('button', { type: 'button', class: 'btn btn--secondary btn--sm', onClick: () => this.load({ append: true }) }, 'Daha fazla yükle')
                : null);
    }

    async remove(item) {
        if (!confirm('Bu analiz kaydını silmek istediğinizden emin misiniz?')) return;
        const ok = await confirmDialog({
            title: 'Analiz kaydı silinsin mi?',
            message: `"${item.source_name || 'Adsız analiz'}" kaydı ve memur kararları kalıcı olarak silinecek. Bu işlem geri alınamaz.`,
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

    async exportAll() {
        try {
            const data = await this.api.exportAllRecords();
            const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `gecmis_${new Date().toISOString().slice(0, 10)}.json`;
            a.click();
            URL.revokeObjectURL(url);
            this.toaster.success(`${data.total || data.records?.length || 0} kayıt dışa aktarıldı.`);
        } catch (error) {
            this.toaster.error(`Dışa aktarma başarısız: ${error.message}`);
        }
    }

    async clearAll() {
        if (!this.items.length) { this.toaster.info('Silinecek kayıt yok.'); return; }
        const ok = await confirmDialog({
            title: 'Tüm kayıtlar silinsin mi?',
            message: `${this.total} analiz kaydı kalıcı olarak silinecek. Bu işlem geri alınamaz.`,
            confirmText: 'Tümünü sil',
            danger: true,
        });
        if (!ok) return;
        try {
            const result = await this.api.clearAllRecords();
            this.toaster.success(`${result.deleted} kayıt silindi.`);
            await this.refresh();
        } catch (error) {
            this.toaster.error(`Silme başarısız: ${error.message}`);
        }
    }

    async importRecords() {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = '.json';
        input.onchange = async () => {
            const file = input.files[0];
            if (!file) return;
            try {
                const text = await file.text();
                const data = JSON.parse(text);
                const records = Array.isArray(data) ? data : (data.records || data.items || []);
                if (!records.length) { this.toaster.info('Dosyada kayıt bulunamadı.'); return; }
                const resp = await this.api.importRecords(records);
                this.toaster.success(`${resp.imported} kayıt içe aktarıldı.`);
                await this.refresh();
            } catch (error) {
                this.toaster.error(`İçe aktarma başarısız: ${error.message}`);
            }
        };
        input.click();
    }

    async exportCsv() {
        try {
            const resp = await fetch('/api/history/export-csv');
            if (!resp.ok) throw new Error('CSV indirilemedi.');
            const blob = await resp.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `gecmis_${new Date().toISOString().slice(0, 10)}.csv`;
            a.click();
            URL.revokeObjectURL(url);
            this.toaster.success('CSV dosyası indirildi.');
        } catch (error) {
            this.toaster.error(`CSV indirme başarısız: ${error.message}`);
        }
    }
}
