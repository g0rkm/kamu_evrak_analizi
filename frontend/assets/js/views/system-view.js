import { ApiClient } from '../core/api.js';
import { h, replace } from '../core/dom.js';

export class SystemView {
    constructor(context) {
        this.ctx = context;
        this.api = context.api || new ApiClient();
        this.el = null;
    }

    get title() {
        return 'Sistem durumu';
    }

    render() {
        if (this.el) return this.el;

        this.bannerTitle = h('div', { style: { fontFamily: 'var(--font-heading)', fontSize: '22px' } }, 'Sistem durumu kontrol ediliyor…');
        this.bannerSub = h('div', { style: { fontSize: '14px', color: 'var(--color-neutral-700)' } }, 'Sunucu ve bağlı servisler sorgulanıyor.');
        this.serverContent = h('div', { style: { display: 'grid', gridTemplateColumns: '1fr auto', gap: '6px', fontSize: '14px' } },
            h('span', null, 'Disk kullanımı'), h('span', { style: { color: 'var(--color-neutral-700)' } }, '…'),
            h('span', null, 'Bellek kullanımı'), h('span', { style: { color: 'var(--color-neutral-700)' } }, '…'));
        this.directoriesContent = h('div', null, h('p', { class: 'card-body', style: { fontSize: '14px' } }, 'Yükleniyor…'));
        this.sessionsContent = h('div', null, h('p', { class: 'card-body', style: { fontSize: '14px' } }, 'Yükleniyor…'));
        this.tasksContent = h('div', null, h('p', { class: 'card-body', style: { fontSize: '14px' } }, 'Yükleniyor…'));
        this.fileTypesContent = h('div', { style: { display: 'flex', gap: '8px', flexWrap: 'wrap' } });

        this.el = h('section', { style: { display: 'flex', flexDirection: 'column', gap: '24px' } },
            h('div', { style: { borderBottom: '1px solid var(--color-divider)', paddingBottom: '18px' } },
                h('div', { class: 'card-kicker' }, 'Bilgi işlem personeli için'),
                h('h1', { style: { margin: '4px 0 0', fontWeight: 400 } }, 'Sistem durumu'),
                h('p', { style: { margin: '4px 0 0', color: 'var(--color-neutral-700)' } }, 'Sunucunun ve bağlı servislerin anlık durumu.')),
            h('div', { class: 'card', style: { padding: '22px', flexDirection: 'row', alignItems: 'center', gap: '18px', borderColor: 'var(--color-accent)', flexWrap: 'wrap' } },
                h('span', { style: { width: '12px', height: '12px', borderRadius: '50%', background: 'var(--color-accent)', flex: 'none' } }),
                h('div', { style: { flex: 1, minWidth: '220px' } }, this.bannerTitle, this.bannerSub),
                h('button', { type: 'button', class: 'btn btn-secondary', onClick: () => this.show() }, 'Yeniden kontrol et')),
            h('div', { style: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '18px' } },
                h('div', { class: 'card', style: { padding: '20px' } }, h('div', { class: 'card-title' }, 'Sunucu'), this.serverContent),
                h('div', { class: 'card', style: { padding: '20px' } }, h('div', { class: 'card-title' }, 'Veri klasörleri'), this.directoriesContent),
                h('div', { class: 'card', style: { padding: '20px' } }, h('div', { class: 'card-title' }, 'Açık oturumlar'), this.sessionsContent),
                h('div', { class: 'card', style: { padding: '20px' } }, h('div', { class: 'card-title' }, 'Zamanlanmış görevler'), this.tasksContent)),
            h('div', { class: 'card', style: { padding: '20px', gap: '12px' } },
                h('div', { class: 'card-title' }, 'Desteklenen dosya türleri'),
                this.fileTypesContent));

        return this.el;
    }

    async show() {
        if (!this.el) this.render();
        await Promise.all([
            this.loadHealthData(),
            this.loadDirectories(),
            this.loadSessions(),
            this.loadFileTypes(),
            this.loadTasks(),
        ]);
    }

    async loadHealthData() {
        try {
            const data = await this.api.request('/system/health-check');
            const disk = data.disk?.used_percent != null ? `%${data.disk.used_percent}` : null;
            const mem = data.memory?.used_percent != null ? `%${data.memory.used_percent}` : null;
            if (data.status === 'healthy' && disk && mem) {
                this.bannerTitle.textContent = 'Tüm servisler çalışıyor';
                this.bannerSub.textContent = 'Sunucu ve bağlı bileşenler normal şekilde yanıt veriyor.';
            } else {
                this.bannerTitle.textContent = 'Dikkat gerektiren bir durum var';
                this.bannerSub.textContent = (!disk || !mem)
                    ? 'Disk ve bellek bilgisi okunamıyor. Analizler çalışıyor; bilgi işlem birimine haber verin.'
                    : `Sistem durumu: ${data.status || 'uyarı'}.`;
            }
            replace(this.serverContent,
                h('span', null, 'Disk kullanımı'), h('span', { style: { color: 'var(--color-neutral-700)' } }, disk || 'Bilinmiyor'),
                h('span', null, 'Bellek kullanımı'), h('span', { style: { color: 'var(--color-neutral-700)' } }, mem || 'Bilinmiyor'));
        } catch {
            this.bannerTitle.textContent = 'Sunucu durumu alınamadı';
            this.bannerSub.textContent = 'Sağlık kontrolü uç noktasına ulaşılamadı.';
        }
    }

    async loadDirectories() {
        try {
            const data = await this.api.request('/system/directories');
            const dirs = Array.isArray(data) ? data : (data.directories || []);
            if (!dirs.length) {
                replace(this.directoriesContent, h('p', { class: 'card-body', style: { fontSize: '14px' } }, 'Kayıtlı klasör bulunamadı.'));
                return;
            }
            replace(this.directoriesContent, h('div', { style: { display: 'grid', gridTemplateColumns: '1fr auto', gap: '6px', fontSize: '14px' } },
                ...dirs.flatMap((d) => [
                    h('span', null, d.name || d.path || '—'),
                    h('span', { style: { color: 'var(--color-neutral-700)' } }, d.exists ? `${d.file_count ?? 0} dosya` : 'Yok'),
                ])));
        } catch {
            replace(this.directoriesContent, h('p', { class: 'error-text', style: { margin: 0, fontSize: '14px' } }, 'Veri klasörleri okunamadı.'));
        }
    }

    async loadSessions() {
        try {
            const data = await this.api.request('/sessions/active');
            const sessions = Array.isArray(data) ? data : (data.sessions || []);
            if (!sessions.length) {
                replace(this.sessionsContent, h('p', { class: 'card-body', style: { fontSize: '14px' } }, 'Şu anda açık oturum yok.'));
                return;
            }
            replace(this.sessionsContent, h('p', { class: 'card-body', style: { fontSize: '14px' } }, `${sessions.length} açık oturum bulunuyor.`));
        } catch {
            replace(this.sessionsContent, h('p', { class: 'error-text', style: { margin: 0, fontSize: '14px' } }, 'Oturum bilgisi alınamadı.'));
        }
    }

    async loadFileTypes() {
        try {
            const data = await this.api.request('/supported-file-types');
            const types = Array.isArray(data) ? data : (data.types || data.extensions || []);
            if (!types.length) {
                replace(this.fileTypesContent, h('span', { class: 'muted' }, 'Tanımlı dosya türü yok.'));
                return;
            }
            replace(this.fileTypesContent, ...types.map((t) => {
                const raw = typeof t === 'string' ? t : (t.extension || t.name || '');
                return h('span', { class: 'tag tag-outline' }, raw.replace(/^\./, '').toUpperCase());
            }));
        } catch {
            replace(this.fileTypesContent, h('span', { class: 'error-text' }, 'Dosya türleri yüklenemedi.'));
        }
    }

    async loadTasks() {
        try {
            const data = await this.api.request('/scheduler/tasks');
            const tasks = Array.isArray(data) ? data : (data.tasks || []);
            if (!tasks.length) {
                replace(this.tasksContent, h('p', { class: 'card-body', style: { fontSize: '14px' } }, 'Tanımlı görev yok.'));
                return;
            }
            replace(this.tasksContent, h('div', { style: { display: 'grid', gridTemplateColumns: '1fr auto', gap: '6px', fontSize: '14px' } },
                ...tasks.flatMap((t) => [
                    h('span', null, t.name || t.id || '—'),
                    h('span', { style: { color: 'var(--color-neutral-700)' } }, t.status || 'Aktif'),
                ])));
        } catch {
            replace(this.tasksContent, h('p', { class: 'error-text', style: { margin: 0, fontSize: '14px' } }, 'Görevler okunamadı.'));
        }
    }
}
