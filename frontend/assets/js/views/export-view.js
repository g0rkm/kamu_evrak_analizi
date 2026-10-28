import { ApiClient } from '../core/api.js';
import { downloadBlob, h, icon, replace } from '../core/dom.js';
import { Vocabulary, fmt } from '../core/vocabulary.js';

export class ExportView {
    title = 'Rapor ve dışa aktarma';

    constructor(container) {
        this._container = container;
        this._api = new ApiClient();
        this._vocab = new Vocabulary();
    }

    async render(root = this._container) {
        this.reportBox = h('div', { id: 'exportReport', hidden: true });

        const exportCard = (id, title, desc, who, cta, fn) => h('div', {
            class: 'card', style: { padding: '28px', alignItems: 'center', textAlign: 'center', gap: '12px' },
        },
            h('span', { style: { width: '50px', height: '50px', borderRadius: '50%', border: '1px solid var(--color-accent)', display: 'grid', placeItems: 'center', color: 'var(--color-accent)', fontSize: '20px' } },
                icon('fileDown')),
            h('div', { style: { fontFamily: 'var(--font-heading)', fontSize: '23px' } }, title),
            h('p', { style: { margin: 0, fontSize: '14px', color: 'var(--color-neutral-700)', flex: 1 } }, desc),
            h('span', { class: 'tag tag-neutral' }, who),
            h('button', { type: 'button', id, class: 'btn btn-primary', style: { width: '100%', padding: '11px' }, onClick: fn }, cta));

        const section = h('section', { style: { display: 'flex', flexDirection: 'column', gap: '26px' } },
            h('div', { style: { textAlign: 'center' } },
                h('h1', { style: { margin: 0, fontWeight: 400 } }, 'Rapor ve dışa aktarma'),
                h('p', { style: { margin: '6px 0 0', color: 'var(--color-neutral-700)' } }, 'Kayıtları bilgisayarınıza indirin veya özet bir rapor alın.')),
            h('div', { style: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '20px' } },
                exportCard('exportCsvBtn', 'Excel tablosu', 'Tüm kayıtları Excel’de açılabilen bir tablo (CSV) olarak indirin.', 'Herkes için', 'Excel olarak indir', () => this._downloadCsv()),
                exportCard('exportReportBtn', 'Özet rapor', 'Evrak sayıları, öncelikler ve onay durumlarını gösteren yazdırılabilir rapor.', 'Amirler için', 'Raporu görüntüle', () => this._showReport()),
                exportCard('exportJsonBtn', 'Veri dosyası (JSON)', 'Başka bir sisteme aktarmak için ham veri dosyası.', 'Bilgi işlem için', 'JSON olarak indir', () => this._downloadJson())),
            this.reportBox);

        replace(root, section);
    }

    async _downloadCsv() {
        try {
            const resp = await fetch('/api/history/export-csv');
            if (resp.ok) {
                downloadBlob(await resp.text(), `kayitlar_${new Date().toISOString().slice(0, 10)}.csv`, 'text/csv;charset=utf-8');
                return;
            }
            const data = await this._api.exportCsv();
            const csv = typeof data === 'string' ? data : (data.csv || JSON.stringify(data));
            downloadBlob(csv, `kayitlar_${new Date().toISOString().slice(0, 10)}.csv`, 'text/csv;charset=utf-8');
        } catch {}
    }

    async _downloadJson() {
        try {
            const data = await this._api.exportAllRecords().catch(() => this._api.exportJsonFile());
            downloadBlob(JSON.stringify(data, null, 2), `kayitlar_${new Date().toISOString().slice(0, 10)}.json`, 'application/json');
        } catch {}
    }

    async _showReport() {
        this.reportBox.hidden = false;
        replace(this.reportBox, h('div', { class: 'card', style: { padding: '24px' } }, 'Rapor hazırlanıyor…'));
        try {
            const data = await this._api.exportReport();
            const byType = Object.entries(data.by_document_type || {});
            const byPrio = Object.entries(data.by_priority || {});
            replace(this.reportBox, h('div', { class: 'card', style: { padding: '26px', gap: '18px' } },
                h('div', { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' } },
                    h('div', null, h('div', { class: 'card-kicker' }, 'Amirler için'), h('div', { class: 'card-title', style: { fontSize: '22px' } }, 'Özet rapor')),
                    h('button', { type: 'button', class: 'btn btn-secondary', onClick: () => window.print() }, 'Yazdır')),
                h('div', { class: 'kpis' },
                    h('div', { class: 'kpi' }, h('div', { class: 'kpi__label' }, 'Toplam kayıt'), h('div', { class: 'kpi__value' }, fmt.number(data.total_records || 0))),
                    h('div', { class: 'kpi' }, h('div', { class: 'kpi__label' }, 'Favori'), h('div', { class: 'kpi__value' }, fmt.number(data.favorite_count || 0))),
                    h('div', { class: 'kpi' }, h('div', { class: 'kpi__label' }, 'Arşivlenen'), h('div', { class: 'kpi__value' }, fmt.number(data.archived_count || 0)))),
                h('div', { class: 'grid-2' },
                    h('div', null,
                        h('div', { class: 'card-kicker', style: { marginBottom: '8px' } }, 'Evrak türü dağılımı'),
                        byType.length ? h('ul', { class: 'list' }, byType.map(([k, v]) => h('li', { class: 'run-item' }, h('span', null, this._vocab.documentType(k)), h('span', { class: 'tnum' }, String(v))))) : h('p', { class: 'muted' }, 'Veri yok.')),
                    h('div', null,
                        h('div', { class: 'card-kicker', style: { marginBottom: '8px' } }, 'Öncelik dağılımı'),
                        byPrio.length ? h('ul', { class: 'list' }, byPrio.map(([k, v]) => h('li', { class: 'run-item' }, h('span', null, this._vocab.priority(k)), h('span', { class: 'tnum' }, String(v))))) : h('p', { class: 'muted' }, 'Veri yok.')))));
        } catch {
            replace(this.reportBox, h('div', { class: 'card', style: { padding: '22px' } }, h('p', { class: 'error-text', style: { margin: 0 } }, 'Rapor yüklenemedi.')));
        }
    }
}
