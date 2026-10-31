import { ApiClient } from '../core/api.js';
import { h, replace } from '../core/dom.js';
import { fmt } from '../core/vocabulary.js';

export class TrendsView {
    title = 'Eğilimler';

    constructor(container) {
        this._container = container;
        this._chart = null;
    }

    async render(root = this._container) {
        this.daysSelect = h('select', { class: 'input', id: 'trendsDays', style: { width: '160px' }, onChange: () => this._loadTrends(parseInt(this.daysSelect.value, 10)) },
            h('option', { value: '7' }, 'Son 7 gün'),
            h('option', { value: '14' }, 'Son 14 gün'),
            h('option', { value: '30', selected: true }, 'Son 30 gün'),
            h('option', { value: '90' }, 'Son 90 gün'));
        this.statsRoot = h('div', { id: 'trendsStats', class: 'kpis' });
        this.chartBox = h('div', { class: 'card', style: { padding: '22px', position: 'relative', height: '320px' } },
            h('canvas', { id: 'trendsChart' }));

        const section = h('section', { style: { display: 'flex', flexDirection: 'column', gap: '24px' } },
            h('div', { class: 'page-bar' },
                h('div', null, h('h1', { style: { margin: 0, fontWeight: 400 } }, 'Analiz eğilimleri'), h('p', { style: { margin: '4px 0 0', color: 'var(--color-neutral-700)' } }, 'Günlük incelenen evrak sayılarını izleyin.')),
                h('div', { class: 'field' }, h('label', { for: 'trendsDays' }, 'Dönem'), this.daysSelect)),
            this.statsRoot,
            this.chartBox);

        replace(root, section);
        await this._loadTrends(30);
    }

    async _loadTrends(days) {
        try {
            const api = new ApiClient();
            const data = await api.trends(days);
            this._renderStats(data.trends || []);
            this._renderChart(data.trends || []);
        } catch {
            replace(this.chartBox, h('p', { class: 'error-text' }, 'Eğilim verileri yüklenemedi.'));
        }
    }

    _renderChart(trends) {
        if (this._chart) this._chart.destroy();
        const canvas = document.getElementById('trendsChart');
        if (!canvas || typeof Chart === 'undefined') return;
        const ctx = canvas.getContext('2d');
        this._chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: trends.map((t) => t.date),
                datasets: [{
                    label: 'Evrak sayısı',
                    data: trends.map((t) => t.count),
                    borderColor: '#b68235',
                    backgroundColor: 'rgba(182, 130, 53, 0.12)',
                    fill: true,
                    tension: 0.3,
                    pointRadius: 3,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { grid: { display: false }, ticks: { maxTicksLimit: 10 } },
                    y: { beginAtZero: true, ticks: { stepSize: 1 } },
                },
            },
        });
    }

    _renderStats(trends) {
        const total = trends.reduce((s, t) => s + t.count, 0);
        const maxDay = trends.reduce((max, t) => t.count > max.count ? t : max, { count: 0 });
        const avg = trends.length > 0 ? (total / trends.length).toLocaleString('tr-TR', { maximumFractionDigits: 1 }) : '0';
        replace(this.statsRoot,
            h('div', { class: 'kpi' }, h('div', { class: 'kpi__label' }, 'Toplam analiz'), h('div', { class: 'kpi__value' }, fmt.number(total))),
            h('div', { class: 'kpi' }, h('div', { class: 'kpi__label' }, 'Günlük ortalama'), h('div', { class: 'kpi__value' }, avg)),
            h('div', { class: 'kpi' }, h('div', { class: 'kpi__label' }, 'En yoğun gün'), h('div', { class: 'kpi__value' }, fmt.number(maxDay.count))));
    }
}
