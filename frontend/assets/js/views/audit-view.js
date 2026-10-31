import { ApiClient } from '../core/api.js';
import { h, replace } from '../core/dom.js';
import { fmt } from '../core/vocabulary.js';

const ACTION_LABELS = {
    analyze: 'Analiz',
    review: 'Onay',
    delete: 'Silme',
    update_tags: 'Etiket güncelleme',
    update_notes: 'Not güncelleme',
    archive: 'Arşivleme',
    unarchive: 'Arşivden çıkarma',
    favorite: 'Favori',
    bulk_delete: 'Toplu silme',
    import_records: 'İçe aktarma',
};

export class AuditView {
    title = 'İşlem kayıtları';

    constructor(container) {
        this._container = container;
        this._api = new ApiClient();
    }

    async render(root = this._container) {
        this.filter = h('select', { class: 'input', id: 'auditActionFilter', style: { width: '180px' }, onChange: () => this._loadLogs() },
            h('option', { value: '' }, 'Tüm işlemler'),
            ...Object.entries(ACTION_LABELS).map(([k, label]) => h('option', { value: k }, label)));
        this.tbody = h('tbody', { id: 'auditLogBody' });
        this.emptyBox = h('div', { style: { textAlign: 'center', padding: '40px 0', display: 'flex', flexDirection: 'column', gap: '6px', alignItems: 'center' } },
            h('div', { style: { fontFamily: 'var(--font-heading)', fontSize: '22px' } }, 'Henüz kayıt yok'),
            h('div', { style: { fontSize: '14px', color: 'var(--color-neutral-700)' } }, 'Bir evrak analiz edildiğinde veya onaylandığında burada görünecek.'));

        const section = h('section', { style: { display: 'flex', flexDirection: 'column', gap: '24px' } },
            h('div', { class: 'page-bar' },
                h('div', null,
                    h('h1', { style: { margin: 0, fontWeight: 400 } }, 'İşlem kayıtları'),
                    h('p', { style: { margin: '4px 0 0', color: 'var(--color-neutral-700)' } }, 'Sistemde kimin, ne zaman, hangi işlemi yaptığı burada tutulur.')),
                h('div', { style: { display: 'flex', gap: '10px', alignItems: 'flex-end' } },
                    h('div', { class: 'field' }, h('label', { for: 'auditActionFilter' }, 'İşlem türü'), this.filter),
                    h('button', { type: 'button', class: 'btn btn-secondary', id: 'auditRefreshBtn', onClick: () => this._loadLogs() }, 'Yenile'))),
            h('div', { class: 'table-wrap' },
                h('table', { class: 'table' },
                    h('thead', null, h('tr', null,
                        h('th', null, 'Zaman'),
                        h('th', null, 'İşlem'),
                        h('th', null, 'Kullanıcı'),
                        h('th', null, 'Kayıt no'),
                        h('th', null, 'Ayrıntı'))),
                    this.tbody)),
            this.emptyBox);

        replace(root, section);
        await this._loadLogs();
    }

    async _loadLogs() {
        const action = this.filter?.value || '';
        try {
            const params = action ? `?action=${encodeURIComponent(action)}` : '';
            const data = await this._api.request(`/audit/logs${params}`);
            this._renderLogs(data.logs || []);
        } catch {
            this.emptyBox.hidden = true;
            replace(this.tbody, h('tr', null, h('td', { colspan: 5, class: 'error-text' }, 'İşlem kayıtları yüklenemedi.')));
        }
    }

    _renderLogs(logs) {
        if (!logs.length) {
            replace(this.tbody);
            this.emptyBox.hidden = false;
            return;
        }
        this.emptyBox.hidden = true;
        const sorted = [...logs].reverse();
        replace(this.tbody, ...sorted.map((l) => h('tr', null,
            h('td', { style: { whiteSpace: 'nowrap', color: 'var(--color-neutral-700)' } }, fmt.date(l.timestamp)),
            h('td', null, h('span', { class: 'tag tag-neutral' }, ACTION_LABELS[l.action] || l.action || '—')),
            h('td', null, l.user || 'sistem'),
            h('td', { class: 'mono' }, l.record_id || '—'),
            h('td', { style: { color: 'var(--color-neutral-700)', fontSize: '13px' } },
                l.details ? (typeof l.details === 'string' ? l.details : JSON.stringify(l.details)).slice(0, 100) : '—'))));
    }
}
