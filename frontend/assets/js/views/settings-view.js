import { ApiClient } from '../core/api.js';
import { h, icon, replace } from '../core/dom.js';
import { fmt } from '../core/vocabulary.js';

const CAPABILITY_LABELS = {
    file_analysis: 'Evrak analizi',
    document_analysis: 'Evrak analizi',
    pii_detection: 'Kişisel veri tespiti',
    audit_logging: 'İşlem kaydı tutma',
    backup: 'Yedekleme',
    backup_restore: 'Yedekleme',
    rate_limiting: 'İstek sınırlama',
    soft_delete: 'Geçici silme',
    bulk_operations: 'Toplu işlemler',
    data_encryption: 'Veri şifreleme',
    notifications: 'Bildirimler',
    csv_export: 'Excel aktarımı',
    json_export: 'JSON aktarımı',
    timeline_view: 'Zaman çizelgesi',
    duplicate_detection: 'Mükerrer evrak tespiti',
    content_search: 'İçerik içinde arama',
    templates: 'Şablonlar',
    search: 'Arama',
    comparison: 'Karşılaştırma',
    rag_legislation: 'Mevzuat eşleştirme',
    ocr: 'Görselden metin okuma',
    human_in_loop: 'Memur onayı',
};

const ENV_LABELS = { development: 'Geliştirme', production: 'Üretim', test: 'Test', testing: 'Test' };
const STATUS_LABELS = { ok: 'Sağlıklı', healthy: 'Sağlıklı', degraded: 'Kısıtlı', warning: 'Uyarılı' };

export class SettingsView {
    title = 'Ayarlar';

    constructor(container) {
        this._container = container;
        this._api = new ApiClient();
    }

    async render(root = this._container) {
        this.reportGrid = h('div', { id: 'systemReport', style: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 0 } },
            h('div', { style: { padding: '10px 14px', color: 'var(--color-neutral-700)' } }, 'Yükleniyor…'));
        this.capsGrid = h('div', { id: 'systemCapabilities', style: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '8px 24px' } });
        this.backupHint = h('p', { class: 'card-body', style: { fontSize: '14px' } },
            'Tüm kayıtların bir kopyasını oluşturun. Son yedek: kontrol ediliyor…');
        this.backupResult = h('div', { id: 'backupResult', style: { fontSize: '14px' } });

        const section = h('section', { style: { display: 'flex', flexDirection: 'column', gap: '24px' } },
            h('div', { style: { borderBottom: '1px solid var(--color-divider)', paddingBottom: '18px' } },
                h('div', { class: 'card-kicker' }, 'Sistem yöneticisi için'),
                h('h1', { style: { margin: '4px 0 0', fontWeight: 400 } }, 'Ayarlar ve sistem bilgileri')),
            h('div', { class: 'card', style: { padding: '22px', gap: '14px' } },
                h('div', { class: 'card-title' }, 'Sistem raporu'),
                this.reportGrid),
            h('div', { class: 'card', style: { padding: '22px', gap: '14px' } },
                h('div', { class: 'card-title' }, 'Açık özellikler'),
                this.capsGrid),
            h('div', { class: 'card', style: { padding: '22px', gap: '12px' } },
                h('div', { class: 'card-title' }, 'Yedekleme'),
                this.backupHint,
                h('div', { style: { display: 'flex', gap: '10px', flexWrap: 'wrap' } },
                    h('button', { type: 'button', id: 'createBackupBtn', class: 'btn btn-primary', onClick: () => this._createBackup() }, 'Şimdi yedek al'),
                    h('button', { type: 'button', id: 'listBackupsBtn', class: 'btn btn-secondary', onClick: () => this._listBackups() }, 'Önceki yedekler')),
                this.backupResult));

        replace(root, section);
        await this._loadData();
    }

    async _loadData() {
        const [report, caps, backups] = await Promise.allSettled([
            this._api.request('/system/report'),
            this._api.request('/system/capabilities'),
            this._api.request('/backup/list'),
        ]);
        this._renderReport(report.status === 'fulfilled' ? report.value : {});
        this._renderCapabilities(caps.status === 'fulfilled' ? caps.value : {});
        if (backups.status === 'fulfilled') {
            const list = backups.value?.backups || [];
            this.backupHint.textContent = list.length
                ? `Tüm kayıtların bir kopyasını oluşturun. Son yedek: ${list[list.length - 1].name}.`
                : 'Tüm kayıtların bir kopyasını oluşturun. Son yedek: henüz alınmadı.';
        } else {
            this.backupHint.textContent = 'Tüm kayıtların bir kopyasını oluşturun. Son yedek: henüz alınmadı.';
        }
    }

    _renderReport(report) {
        const errPct = ((report.metrics?.error_rate || 0) * 100).toLocaleString('tr-TR', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
        const items = [
            ['Sürüm', report.version || '—'],
            ['Ortam', ENV_LABELS[report.environment] || report.environment || '—'],
            ['Durum', STATUS_LABELS[report.health?.status] || report.health?.status || '—'],
            ['Çalışma süresi', fmt.seconds(report.uptime_seconds)],
            ['Toplam istek', fmt.number(report.metrics?.total_requests || 0)],
            ['Hata oranı', `%${errPct}`],
        ];
        replace(this.reportGrid, ...items.map(([k, v]) => h('div', { style: { padding: '10px 14px', borderLeft: '1px solid var(--color-divider)' } },
            h('div', { style: { fontSize: '12px', color: 'var(--color-neutral-700)' } }, k),
            h('div', { style: { fontSize: '16px' } }, v))));
    }

    _renderCapabilities(caps) {
        const features = Object.entries(caps?.features || CAPABILITY_LABELS);
        replace(this.capsGrid, ...features.map(([k, v]) => h('div', {
            style: { display: 'flex', gap: '8px', alignItems: 'center', fontSize: '14px', padding: '6px 0', borderBottom: '1px solid var(--color-divider)', opacity: v === false ? 0.5 : 1 },
        },
            h('span', { style: { color: 'var(--color-accent)', display: 'inline-flex' } }, icon(v === false ? 'minus' : 'check')),
            CAPABILITY_LABELS[k] || k.replace(/_/g, ' '))));
    }

    async _createBackup() {
        try {
            const result = await this._api.request('/backup/create', { method: 'POST', json: {} });
            replace(this.backupResult, h('span', { class: 'success-text' },
                `Yedek oluşturuldu (${result.file_count || 0} dosya, ${((result.size_bytes || 0) / 1024).toFixed(1)} KB).`));
            await this._loadData();
        } catch {
            replace(this.backupResult, h('span', { class: 'error-text' }, 'Yedek oluşturulamadı.'));
        }
    }

    async _listBackups() {
        try {
            const data = await this._api.request('/backup/list');
            const list = data.backups || [];
            if (!list.length) {
                replace(this.backupResult, h('span', { class: 'muted' }, 'Henüz alınmış yedek yok.'));
                return;
            }
            replace(this.backupResult, h('ul', { class: 'list' },
                ...list.map((b) => h('li', { class: 'run-item' },
                    h('span', null, b.name),
                    h('span', { class: 'muted tnum' }, `${((b.size_bytes || 0) / 1024).toFixed(1)} KB`)))));
        } catch {
            replace(this.backupResult, h('span', { class: 'error-text' }, 'Yedekler okunamadı.'));
        }
    }
}
