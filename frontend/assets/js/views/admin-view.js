import { downloadBlob, h, replace } from '../core/dom.js';
import { fmt } from '../core/vocabulary.js';

const SERVICE_LABELS = {
    audit: 'İşlem kaydı',
    audit_logger: 'İşlem kaydı',
    backup: 'Yedekleme',
    backup_service: 'Yedekleme',
    webhooks: 'Dış bağlantılar',
    webhook_service: 'Dış bağlantılar',
    integrity: 'Veri bütünlüğü',
    integrity_service: 'Veri bütünlüğü',
    notifications: 'Bildirimler',
    notification_service: 'Bildirimler',
    templates: 'Şablonlar',
    template_service: 'Şablonlar',
    auth: 'Kimlik doğrulama',
    auth_service: 'Kimlik doğrulama',
    scheduler: 'Zamanlayıcı',
    scheduler_service: 'Zamanlayıcı',
    file_validator: 'Dosya kontrolü',
    session_manager: 'Oturum yönetimi',
    health_checker: 'Sağlık kontrolü',
    metrics: 'Ölçümler',
    metrics_service: 'Ölçümler',
    log_service: 'Kayıt servisi',
    data_export: 'Dışa aktarma',
    export_service: 'Dışa aktarma',
    maintenance: 'Bakım',
    maintenance_service: 'Bakım',
    error_tracker: 'Hata takibi',
    correlation: 'İlişkilendirme',
    correlation_service: 'İlişkilendirme',
    sanitizer: 'Temizleme',
    request_validator: 'İstek doğrulama',
    health_monitor: 'Sağlık izleme',
    profiler: 'Performans',
    performance_profiler: 'Performans',
    webhook_retry: 'Bağlantı tekrarı',
    backup_verifier: 'Yedek doğrulama',
    data_encryption: 'Veri şifreleme',
};

const LEVEL_LABELS = { INFO: 'Bilgi', WARNING: 'Uyarı', ERROR: 'Hata' };

export default class AdminView {
    title = 'Yönetim paneli';

    constructor(api) {
        this.api = api;
    }

    async render(container) {
        this.maintFooter = h('div', { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px' } },
            h('span', { class: 'tag tag-neutral' }, '…'));
        this.uptimeVal = h('div', { style: { fontFamily: 'var(--font-heading)', fontSize: '36px' } }, '—');
        this.uptimeHint = h('div', { style: { fontSize: '12px', color: 'var(--color-neutral-700)' } }, ' ');
        this.recentLogsBox = h('div', { style: { display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '13px' } }, 'Yükleniyor…');
        this.servicesCount = h('span', { style: { fontSize: '13px', color: 'var(--color-neutral-700)' } }, '—');
        this.servicesGrid = h('div', { style: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '0 24px' } });
        this.validateInput = h('input', { class: 'input', id: 'validate-input', placeholder: 'Denemek istediğiniz metni girin…' });
        this.validateResult = h('div', { id: 'validate-result', hidden: true, style: { fontSize: '14px' } });

        const section = h('section', { style: { display: 'flex', flexDirection: 'column', gap: '24px' } },
            h('div', { style: { borderBottom: '1px solid var(--color-divider)', paddingBottom: '18px' } },
                h('div', { class: 'card-kicker' }, 'Sistem yöneticisi için'),
                h('h1', { style: { margin: '4px 0 0', fontWeight: 400 } }, 'Yönetim paneli')),
            h('div', { style: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '18px' } },
                h('div', { class: 'card', style: { padding: '20px', gap: '12px' } },
                    h('div', { class: 'card-title' }, 'Bakım modu'),
                    h('p', { class: 'card-body', style: { fontSize: '13px' } }, 'Açıkken kullanıcılar yeni analiz başlatamaz.'),
                    this.maintFooter),
                h('div', { class: 'card', style: { padding: '20px', textAlign: 'center' } },
                    h('div', { class: 'card-title', style: { textAlign: 'left' } }, 'Çalışma süresi'),
                    this.uptimeVal,
                    this.uptimeHint),
                h('div', { class: 'card', style: { padding: '20px' } },
                    h('div', { class: 'card-title' }, 'Son kayıtlar'),
                    this.recentLogsBox),
                h('div', { class: 'card', style: { padding: '20px', textAlign: 'center' } },
                    h('div', { class: 'card-title', style: { textAlign: 'left' } }, 'Ortalama işlem süresi'),
                    this.avgTimeVal = h('div', { style: { fontFamily: 'var(--font-heading)', fontSize: '36px' } }, '—'),
                    h('div', { style: { fontSize: '12px', color: 'var(--color-neutral-700)' } }, 'Evrak başına')),
                h('div', { class: 'card', style: { padding: '20px', gap: '12px' } },
                    h('div', { class: 'card-title' }, 'Veri dışa aktarma'),
                    h('p', { class: 'card-body', style: { fontSize: '13px' } }, 'Tüm kayıtları JSON formatında indirin.'),
                    h('button', { type: 'button', class: 'btn btn-primary', style: { alignSelf: 'flex-start' }, onClick: () => this.downloadJson() }, 'JSON olarak indir'))),
            h('div', { class: 'card', style: { padding: '20px', gap: '14px' } },
                h('div', { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' } },
                    h('div', { class: 'card-title' }, 'Servisler'),
                    this.servicesCount),
                this.servicesGrid),
            h('div', { class: 'card', style: { padding: '20px', gap: '10px' } },
                h('div', { class: 'card-title' }, 'Girdi doğrulama testi'),
                h('div', { style: { display: 'flex', gap: '10px', flexWrap: 'wrap' } },
                    this.validateInput,
                    h('button', { type: 'button', id: 'btn-validate', class: 'btn btn-primary', onClick: () => this.validateInputText() }, 'Doğrula')),
                this.validateResult));

        replace(container, section);
        await this.loadData();
    }

    async loadData() {
        const results = await Promise.allSettled([
            this.api.request('/maintenance/status'),
            this.api.request('/system/config-report'),
            this.api.request('/system/uptime'),
            this.api.logsRecent(),
            this.api.request('/history/stats'),
        ]);
        const [maint, config, uptime, logs, stats] = results;
        this.renderMaintenance(maint.status === 'fulfilled' ? maint.value : null);
        this.renderServices(config.status === 'fulfilled' ? config.value : null);
        this.renderSystemInfo(uptime.status === 'fulfilled' ? uptime.value : null);
        this.renderLogs(logs.status === 'fulfilled' ? logs.value : null);
        const statsVal = stats?.status === 'fulfilled' ? stats.value : null;
        if (statsVal?.avg_processing_time != null) {
            this.avgTimeVal.textContent = fmt.seconds(statsVal.avg_processing_time);
        }
    }

    renderMaintenance(data) {
        const active = !!data?.maintenance_mode;
        const btn = h('button', {
            type: 'button', id: 'btnMaintenanceToggle', class: `btn ${active ? 'btn-secondary' : 'btn-primary'}`,
            onClick: async () => {
                if (active) await this.api.maintenanceDisable();
                else await this.api.maintenanceEnable(prompt('Bakım nedeni (isteğe bağlı):') || '');
                await this.loadData();
            },
        }, active ? 'Bakım modunu kapat' : 'Bakım modunu aç');
        replace(this.maintFooter,
            h('span', { class: `tag ${active ? 'tag-accent' : 'tag-neutral'}` }, active ? 'Açık' : 'Kapalı'),
            btn);
    }

    renderServices(data) {
        const services = data?.services || SERVICE_LABELS;
        const entries = Object.entries(services);
        const activeCount = entries.filter(([, v]) => v !== false).length;
        this.servicesCount.textContent = `${activeCount} / ${entries.length} çalışıyor`;
        replace(this.servicesGrid, ...entries.map(([key, active]) => {
            const ok = active !== false;
            return h('div', { style: { display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 0', borderBottom: '1px solid var(--color-divider)', fontSize: '13px' } },
                h('span', { style: { width: '7px', height: '7px', borderRadius: '50%', background: ok ? 'var(--color-accent)' : 'var(--color-neutral-400)' } }),
                h('span', { style: { flex: 1 } }, SERVICE_LABELS[key] || key.replace(/_/g, ' ')),
                h('span', { style: { color: 'var(--color-neutral-700)', fontSize: '12px' } }, ok ? 'Aktif' : 'Pasif'));
        }));
    }

    renderSystemInfo(data) {
        const sec = data?.uptime_seconds || 0;
        this.uptimeVal.textContent = fmt.seconds(sec);
        if (sec > 0) {
            const started = new Date(Date.now() - sec * 1000).toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' });
            this.uptimeHint.textContent = `Son başlatma: ${started}`;
        }
    }

    renderLogs(data) {
        const logs = data?.logs || [];
        if (!logs.length) {
            replace(this.recentLogsBox, h('span', { class: 'muted' }, 'Henüz kayıt yok.'));
            return;
        }
        replace(this.recentLogsBox, ...logs.slice(-4).reverse().map((log) => h('div', { style: { fontSize: '13px', display: 'flex', gap: '8px', alignItems: 'baseline' } },
            h('span', { class: 'tag tag-neutral' }, LEVEL_LABELS[log.level] || log.level || 'Bilgi'),
            h('span', { style: { overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } },
                `${log.timestamp?.substring(11, 19) || ''} ${log.message || ''}`))));
    }

    async downloadJson() {
        try {
            const data = await this.api.exportAllRecords().catch(() => this.api.exportJsonFile());
            downloadBlob(JSON.stringify(data, null, 2), `kayitlar_${new Date().toISOString().slice(0, 10)}.json`, 'application/json');
        } catch {}
    }

    async validateInputText() {
        const text = this.validateInput.value;
        this.validateResult.hidden = false;
        try {
            const data = await this.api.sanitizeCheck(text);
            replace(this.validateResult, data.safe
                ? h('span', { class: 'success-text' }, 'Güvenli girdi — zararlı kalıp tespit edilmedi.')
                : h('span', { class: 'error-text' }, `Tehdit tespit edildi: ${(data.threats || []).join(', ')}`));
        } catch (e) {
            replace(this.validateResult, h('span', { class: 'error-text' }, `Doğrulama hatası: ${e.message}`));
        }
    }
}
