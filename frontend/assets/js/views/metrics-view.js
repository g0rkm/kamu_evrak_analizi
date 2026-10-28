import { h, replace } from '../core/dom.js';
import { fmt } from '../core/vocabulary.js';

function fmtMs(value) {
    const n = Number(value) || 0;
    return `${n.toLocaleString('tr-TR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })} ms`;
}

export default class MetricsView {
    title = 'Teknik ölçümler';

    constructor(api) {
        this.api = api;
    }

    async render(container) {
        this.statsGrid = h('div', { style: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: '16px' } });
        this.topBody = h('tbody');
        this.slowBody = h('tbody');
        this.logCard = h('div', { class: 'card', style: { padding: '20px', display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', textAlign: 'center' } });

        const section = h('section', { style: { display: 'flex', flexDirection: 'column', gap: '24px' } },
            h('div', { style: { borderBottom: '1px solid var(--color-divider)', paddingBottom: '18px' } },
                h('div', { class: 'card-kicker' }, 'Bilgi işlem personeli için'),
                h('h1', { style: { margin: '4px 0 0', fontWeight: 400 } }, 'Teknik ölçümler'),
                h('p', { style: { margin: '4px 0 0', color: 'var(--color-neutral-700)' } },
                    'Sistemin hızını ve hatalarını izlemek için kullanılır. Günlük işleriniz için bu sayfaya ihtiyacınız yoktur.')),
            this.statsGrid,
            h('div', { style: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: '20px' } },
                h('div', { class: 'card', style: { padding: '20px' } },
                    h('div', { class: 'card-title' }, 'En çok kullanılan servisler'),
                    h('table', { class: 'table', style: { fontSize: '13px' } },
                        h('thead', null, h('tr', null,
                            h('th', null, 'Adres'),
                            h('th', { style: { textAlign: 'right' } }, 'İstek'),
                            h('th', { style: { textAlign: 'right' } }, 'Ort. süre'))),
                        this.topBody)),
                h('div', { class: 'card', style: { padding: '20px' } },
                    h('div', { class: 'card-title' }, 'En yavaş servisler'),
                    h('table', { class: 'table', style: { fontSize: '13px' } },
                        h('thead', null, h('tr', null,
                            h('th', null, 'Adres'),
                            h('th', { style: { textAlign: 'right' } }, 'Ort. süre'),
                            h('th', { style: { textAlign: 'right' } }, 'İstek'))),
                        this.slowBody))),
            this.logCard);

        replace(container, section);
        await this.loadData();
    }

    async loadData() {
        const [summary, status, top, slowest, logStats] = await Promise.allSettled([
            this.api.metricsSummary(),
            this.api.metricsStatusDist(),
            this.api.metricsTopEndpoints(),
            this.api.metricsSlowest(),
            this.api.logsStats(),
        ]);
        this.renderSummary(
            summary.status === 'fulfilled' ? summary.value : null,
            status.status === 'fulfilled' ? status.value : null,
        );
        this.renderTop(top.status === 'fulfilled' ? top.value : null);
        this.renderSlowest(slowest.status === 'fulfilled' ? slowest.value : null);
        this.renderLogStats(logStats.status === 'fulfilled' ? logStats.value : null);
    }

    renderSummary(data, statusDist) {
        const total = data?.total_requests || 0;
        const avg = Math.round(data?.avg_duration_ms || 0);
        const errRate = (data?.error_rate || 0).toLocaleString('tr-TR', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
        const okCount = statusDist
            ? Object.entries(statusDist).filter(([k]) => k.startsWith('2')).reduce((s, [, n]) => s + (Number(n) || 0), 0)
            : total;
        const items = [
            ['Toplam istek', fmt.number(total)],
            ['Ort. yanıt süresi', `${avg} ms`],
            ['Hata oranı', `%${errRate}`],
            ['Başarılı yanıt', fmt.number(okCount || total)],
        ];
        replace(this.statsGrid, ...items.map(([label, value]) => h('div', {
            class: 'card', style: { padding: '18px', textAlign: 'center', alignItems: 'center', gap: '2px' },
        },
            h('div', { class: 'card-kicker' }, label),
            h('div', { style: { fontFamily: 'var(--font-heading)', fontSize: '34px', fontVariantNumeric: 'tabular-nums' } }, value))));
    }

    renderTop(data) {
        const rows = data?.top || [];
        if (!rows.length) {
            replace(this.topBody, h('tr', null, h('td', { colspan: 3, class: 'muted' }, 'Henüz veri yok')));
            return;
        }
        replace(this.topBody, ...rows.map((e) => h('tr', null,
            h('td', { class: 'mono' }, e.path || e.endpoint || ''),
            h('td', { class: 'tnum', style: { textAlign: 'right' } }, String(e.count ?? e.requests ?? 0)),
            h('td', { class: 'tnum', style: { textAlign: 'right' } }, fmtMs(e.avg_duration_ms ?? e.avg_ms)))));
    }

    renderSlowest(data) {
        const rows = data?.slowest || [];
        if (!rows.length) {
            replace(this.slowBody, h('tr', null, h('td', { colspan: 3, class: 'muted' }, 'Henüz veri yok')));
            return;
        }
        replace(this.slowBody, ...rows.map((e) => h('tr', null,
            h('td', { class: 'mono' }, e.path || e.endpoint || ''),
            h('td', { class: 'tnum', style: { textAlign: 'right' } }, fmtMs(e.avg_duration_ms ?? e.avg_ms)),
            h('td', { class: 'tnum', style: { textAlign: 'right' } }, String(e.count ?? e.requests ?? 0)))));
    }

    renderLogStats(data) {
        const mem = fmt.number(data?.recent_in_memory || 0);
        const files = fmt.number(data?.log_files || 0);
        const size = (data?.total_size_human || '0 B').replace('.', ',');
        replace(this.logCard,
            h('div', null, h('div', { class: 'card-kicker' }, 'Bellekteki kayıt'), h('div', { style: { fontFamily: 'var(--font-heading)', fontSize: '30px' } }, mem)),
            h('div', { style: { borderLeft: '1px solid var(--color-divider)' } }, h('div', { class: 'card-kicker' }, 'Kayıt dosyası'), h('div', { style: { fontFamily: 'var(--font-heading)', fontSize: '30px' } }, files)),
            h('div', { style: { borderLeft: '1px solid var(--color-divider)' } }, h('div', { class: 'card-kicker' }, 'Toplam boyut'), h('div', { style: { fontFamily: 'var(--font-heading)', fontSize: '30px' } }, size)));
    }
}
