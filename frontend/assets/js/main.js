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
                    this.toaster.info('Kısayollar: 1=Analiz, 2=Geçmiş, 3=Karşılaştır');
                    break;
            }
        });

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
