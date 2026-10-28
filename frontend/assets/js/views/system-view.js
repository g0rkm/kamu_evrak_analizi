import { h, append, replace } from '../core/dom.js';
import { ApiClient } from '../core/api.js';

export class SystemView {
    constructor(context) {
        this.ctx = context;
        this.api = context.api || new ApiClient();
        this.el = null;
    }

    get title() {
        return "Sistem Durumu";
    }

    render() {
        if (this.el) return this.el;

        // Ana Konteyner
        const container = h('div', { class: 'system-view-container' },
            h('h2', { class: 'section-title' }, 'Sistem Durumu'),
            
            // 3 kart bölümü yan yana (CSS grid yapısı için sınıf)
            this.gridSection = h('div', { class: 'system-grid-3' },
                this.healthCard = h('div', { class: 'card health-card' },
                    h('h3', {}, 'Sunucu Sağlığı'),
                    this.healthContent = h('div', { class: 'card-content' }, 'Yükleniyor...')
                ),
                this.directoriesCard = h('div', { class: 'card directories-card' },
                    h('h3', {}, 'Veri Dizinleri'),
                    this.directoriesContent = h('div', { class: 'card-content' }, 'Yükleniyor...')
                ),
                this.sessionsCard = h('div', { class: 'card sessions-card' },
                    h('h3', {}, 'Aktif Oturumlar'),
                    this.sessionsContent = h('div', { class: 'card-content' }, 'Yükleniyor...')
                )
            ),

            // Alt bölüm kartları
            this.bottomGrid = h('div', { class: 'system-grid-2' },
                this.fileTypesCard = h('div', { class: 'card file-types-card' },
                    h('h3', {}, 'Desteklenen Dosya Türleri'),
                    this.fileTypesContent = h('div', { class: 'card-content' }, 'Yükleniyor...')
                ),
                this.tasksCard = h('div', { class: 'card tasks-card' },
                    h('h3', {}, 'Zamanlayıcı Görevleri'),
                    this.tasksContent = h('div', { class: 'card-content' }, 'Yükleniyor...')
                )
            )
        );

        this.el = container;
        return this.el;
    }

    async show() {
        if (!this.el) {
            this.render();
        }
        // Tüm verileri paralel olarak fetch et ve kartları doldur
        await Promise.all([
            this.loadHealthData(),
            this.loadDirectories(),
            this.loadSessions(),
            this.loadFileTypes(),
            this.loadTasks()
        ]);
    }

    async loadHealthData() {
        try {
            const data = await this.api.request('/system/health-check');
            
            let badgeClass = 'badge-secondary';
            let statusText = data.status || 'Bilinmiyor';
            
            if (data.status === 'healthy') {
                badgeClass = 'badge-success';
                statusText = 'Sağlıklı';
            } else if (data.status === 'degraded') {
                badgeClass = 'badge-warning';
                statusText = 'Hassas / Uyarılı';
            } else if (data.status === 'unhealthy') {
                badgeClass = 'badge-danger';
                statusText = 'Sorunlu';
            }

            const content = h('div', {},
                h('div', { class: 'health-status-row' },
                    h('span', {}, 'Durum: '),
                    h('span', { class: `badge ${badgeClass}` }, statusText)
                ),
                h('div', { class: 'health-metrics' },
                    h('p', {}, `Disk Kullanımı: ${data.disk_usage_percent ?? 'N/A'}%`),
                    h('p', {}, `Bellek Kullanımı: ${data.memory_usage_percent ?? 'N/A'}%`)
                )
            );

            replace(this.healthContent, content);
        } catch (err) {
            replace(this.healthContent, h('p', { class: 'error-text' }, 'Sağlık bilgileri yüklenemedi.'));
        }
    }

    async loadDirectories() {
        try {
            const data = await this.api.request('/system/directories');
            const dirs = Array.isArray(data) ? data : (data.directories || []);

            if (dirs.length === 0) {
                replace(this.directoriesContent, h('p', {}, 'Kayıtlı dizin bulunamadı.'));
                return;
            }

            const rows = dirs.map(dir => 
                h('tr', {},
                    h('td', {}, dir.name || dir.path || '-'),
                    h('td', {}, dir.exists ? 'Var' : 'Yok'),
                    h('td', {}, dir.writable ? 'Evet' : 'Hayır'),
                    h('td', {}, String(dir.file_count ?? 0))
                )
            );

            const table = h('table', { class: 'data-table' },
                h('thead', {},
                    h('tr', {},
                        h('th', {}, 'İsim'),
                        h('th', {}, 'Durum'),
                        h('th', {}, 'Yazılabilir'),
                        h('th', {}, 'Dosya Sayısı')
                    )
                ),
                h('tbody', {}, rows)
            );

            replace(this.directoriesContent, table);
        } catch (err) {
            replace(this.directoriesContent, h('p', { class: 'error-text' }, 'Veri dizinleri yüklenemedi.'));
        }
    }

    async loadSessions() {
        try {
            const data = await this.api.request('/sessions/active');
            const sessions = Array.isArray(data) ? data : (data.sessions || []);

            const countInfo = h('p', { class: 'session-count-info' }, `Aktif Oturum Sayısı: ${sessions.length}`);

            if (sessions.length === 0) {
                replace(this.sessionsContent, h('div', {}, countInfo, h('p', {}, 'Aktif oturum bulunmuyor.')));
                return;
            }

            const rows = sessions.map(session => 
                h('tr', {},
                    h('td', {}, session.id || session.session_id || '-'),
                    h('td', {}, session.username || session.user || 'Anonim'),
                    h('td', {}, session.ip_address || '-')
                )
            );

            const table = h('table', { class: 'data-table' },
                h('thead', {},
                    h('tr', {},
                        h('th', {}, 'Oturum ID'),
                        h('th', {}, 'Kullanıcı'),
                        h('th', {}, 'IP Adresi')
                    )
                ),
                h('tbody', {}, rows)
            );

            replace(this.sessionsContent, h('div', {}, countInfo, table));
        } catch (err) {
            replace(this.sessionsContent, h('p', { class: 'error-text' }, 'Aktif oturumlar yüklenemedi.'));
        }
    }

    async loadFileTypes() {
        try {
            const data = await this.api.request('/supported-file-types');
            const types = Array.isArray(data) ? data : (data.types || data.extensions || []);

            if (types.length === 0) {
                replace(this.fileTypesContent, h('p', {}, 'Desteklenen dosya türü bulunamadı.'));
                return;
            }

            const badges = types.map(type => 
                h('span', { class: 'badge badge-outline' }, typeof type === 'string' ? type : (type.extension || type.name))
            );

            const badgeContainer = h('div', { class: 'badge-container' }, badges);
            replace(this.fileTypesContent, badgeContainer);
        } catch (err) {
            replace(this.fileTypesContent, h('p', { class: 'error-text' }, 'Dosya türleri yüklenemedi.'));
        }
    }

    async loadTasks() {
        try {
            const data = await this.api.request('/scheduler/tasks');
            const tasks = Array.isArray(data) ? data : (data.tasks || []);

            if (tasks.length === 0) {
                replace(this.tasksContent, h('p', {}, 'Tanımlı zamanlayıcı görevi bulunmuyor.'));
                return;
            }

            const rows = tasks.map(task => 
                h('tr', {},
                    h('td', {}, task.name || task.id || '-'),
                    h('td', {}, task.status || '-'),
                    h('td', {}, task.next_run || task.schedule || '-')
                )
            );

            const table = h('table', { class: 'data-table' },
                h('thead', {},
                    h('tr', {},
                        h('th', {}, 'Görev Adı'),
                        h('th', {}, 'Durum'),
                        h('th', {}, 'Sonraki Çalışma')
                    )
                ),
                h('tbody', {}, rows)
            );

            replace(this.tasksContent, table);
        } catch (err) {
            replace(this.tasksContent, h('p', { class: 'error-text' }, 'Zamanlayıcı görevleri yüklenemedi.'));
        }
    }
}
