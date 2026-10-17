import { ApiClient } from './core/api.js';
import { hydrateIcons } from './core/icons.js';
import { ThemeController, Toaster } from './core/ui.js';
import { Vocabulary } from './core/vocabulary.js';
import { AnalyzeView } from './views/analyze-view.js';
import { CompareView } from './views/compare-view.js';
import { HistoryView } from './views/history-view.js';

/** Üst bardaki sistem durumu göstergesi; sağlık uç noktasını periyodik olarak sorgular. */
class SystemStatus {
    static INTERVAL = 60_000;

    constructor(element, api) {
        this.element = element;
        this.text = element.querySelector('.status-pill__text');
        this.api = api;
        element.style.cursor = 'pointer';
        element.addEventListener('click', () => this.showDetails());
    }

    start() {
        this.check();
        setInterval(() => this.check(), SystemStatus.INTERVAL);
    }

    async check() {
        try {
            const health = await this.api.health();
            if (!health.llm_configured) {
                this.set('warn', 'LLM yapılandırılmamış', 'Sunucuda LLM_API_KEY tanımlı değil; analizler çalışmayacak.');
            } else if (!health.rag_available) {
                this.set('warn', 'Mevzuat indeksi yok', 'RAG indeksi bulunamadı; mevzuat eşleştirme yalnızca metadata ile yapılır. (scripts/build_index.py)');
            } else {
                this.set('ok', 'Sistem hazır', `Model: ${health.llm_model} · ${health.rag_chunks} mevzuat parçası · sürüm ${health.version}`);
            }
        } catch {
            this.set('down', 'Sunucuya ulaşılamıyor', 'API yanıt vermiyor. Sunucunun çalıştığından emin olun.');
        }
    }

    set(state, text, title) {
        this.element.dataset.state = state;
        this.text.textContent = text;
        this.element.title = title;
        this.element.setAttribute('aria-label', title);
    }

    async showDetails() {
        try {
            const [health, sysInfo, detailed] = await Promise.all([
                this.api.health(),
                this.api.systemInfo().catch(() => null),
                this.api.healthDetailed().catch(() => null),
            ]);
            const info = [
                `Sürüm: ${health.version}`,
                `Durum: ${health.status}`,
                `Ortam: ${health.environment || 'development'}`,
                `Model: ${health.llm_model}`,
                `LLM: ${health.llm_configured ? 'Yapılandırılmış' : 'Yapılandırılmamış'}`,
                `RAG: ${health.rag_available ? `${health.rag_chunks} parça` : 'Yok'}`,
                `Toplam analiz: ${health.total_analyses}`,
                `Çalışma süresi: ${sysInfo?.uptime_human || Math.round(health.uptime_seconds / 60) + ' dk'}`,
                health.disk_free_mb != null ? `Disk: ${health.disk_free_mb} MB boş` : null,
                detailed ? `\nAlt sistemler: ${detailed.status}\n• LLM: ${detailed.checks.llm.configured ? 'Yapılandırılmış' : 'Yok'}${detailed.checks.llm.circuit_breaker_closed ? '' : ' (devre kesici açık!)'}\n• Depolama: ${detailed.checks.storage.free_mb} MB boş${detailed.checks.storage.warning ? ' ⚠' : ''}\n• RAG: ${detailed.checks.rag.available ? detailed.checks.rag.chunks + ' parça' : 'Yok'}` : null,
                health.warnings?.length ? `\nUyarılar:\n${health.warnings.map(w => '⚠ ' + w).join('\n')}` : null,
            ].filter(Boolean).join('\n');
            alert(info);
        } catch {
            alert('Sistem bilgisi alınamadı.');
        }
    }
}

/** Hash tabanlı yönlendirme: #/analiz, #/analiz/<kayıt>, #/gecmis, #/karsilastir */
class App {
    constructor() {
        this.api = new ApiClient();
        this.toaster = new Toaster(document.getElementById('toaster'));
        this.root = document.getElementById('viewRoot');
        this.navLinks = [...document.querySelectorAll('.main-nav a[data-route]')];
    }

    async start() {
        hydrateIcons();
        new ThemeController(document.getElementById('themeToggle'));
        new SystemStatus(document.getElementById('systemStatus'), this.api).start();

        let meta = null;
        try {
            meta = await this.api.meta();
        } catch (error) {
            this.toaster.error(`Sistem bilgileri yüklenemedi: ${error.message}`);
        }
        try {
            const health = await this.api.health();
            if (health.status === 'degraded') {
                this.toaster.warn('Yapay zekâ servisi yapılandırılmamış. Analizler çalışmayacak.');
            } else if (health.status === 'warning') {
                this.toaster.warn('Sistem uyarısı: disk alanı düşük.');
            }
            if (health.warnings?.length) {
                health.warnings.forEach(w => this.toaster.warn(w));
            }
        } catch {}
        const context = {
            api: this.api,
            vocab: new Vocabulary(meta || undefined),
            toaster: this.toaster,
            navigate: (hash) => this.navigate(hash),
        };
        this.views = {
            analiz: new AnalyzeView(context),
            gecmis: new HistoryView(context),
            karsilastir: new CompareView(context),
        };

        window.addEventListener('hashchange', () => this.route());
        this.route();

        // Klavye kısayolları
        document.addEventListener('keydown', (e) => {
            // Input/textarea içindeyken kısayolları devre dışı bırak
            if (e.target.matches('input, textarea, select, [contenteditable]')) return;
            if (e.ctrlKey || e.metaKey || e.altKey) return;

            switch (e.key) {
                case '1': e.preventDefault(); this.navigate('#/analiz'); break;
                case '2': e.preventDefault(); this.navigate('#/gecmis'); break;
                case '3': e.preventDefault(); this.navigate('#/karsilastir'); break;
                case '?':
                    e.preventDefault();
                    alert('Klavye kısayolları:\n\n1 — Analiz sayfası\n2 — Geçmiş sayfası\n3 — Karşılaştır sayfası\n? — Bu yardım penceresi\n\nAnaliz sayfasında:\nCtrl+Enter — Analizi başlat');
                    break;
            }
        });

        // Versiyon kontrolü
        try {
            const config = await this.api.configExportData();
            if (config && config.maintenance_mode) {
                this.toaster.warn('Sistem bakım modundadır. Bazı işlemler kısıtlı olabilir.');
            }
        } catch {}

        window.addEventListener('offline', () => this.toaster.warn('İnternet bağlantısı kesildi.'));
        window.addEventListener('online', () => this.toaster.success('İnternet bağlantısı yeniden kuruldu.'));
    }

    navigate(hash) {
        if (location.hash !== hash) location.hash = hash;
    }

    route() {
        const [name, id] = location.hash.replace(/^#\/?/, '').split('/');
        const routeName = this.views[name] ? name : 'analiz';
        const view = this.views[routeName];

        if (this.currentView !== view) {
            this.root.replaceChildren(view.element);
            this.currentView = view;
            window.scrollTo({ top: 0 });
        }
        this.navLinks.forEach((link) => {
            if (link.dataset.route === routeName) link.setAttribute('aria-current', 'page');
            else link.removeAttribute('aria-current');
        });
        document.title = `${view.title} · Kamu Evrak Analizi`;
        view.show({ id: id ? decodeURIComponent(id) : null });
    }
}

new App().start();
