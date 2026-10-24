export default class MetricsView {
    constructor(api) {
        this.api = api;
    }

    async render(container) {
        container.innerHTML = `
            <section class="view-section">
                <h1>API Metrikleri</h1>
                <div class="metrics-grid">
                    <div class="card" id="metricsSummaryCard">
                        <div class="card__header"><h3>Genel Ozet</h3></div>
                        <div class="card__body" id="metricsSummary">Yukleniyor...</div>
                    </div>
                    <div class="card" id="metricsStatusCard">
                        <div class="card__header"><h3>Durum Dagilimi</h3></div>
                        <div class="card__body" id="metricsStatus">Yukleniyor...</div>
                    </div>
                    <div class="card" id="metricsTopCard">
                        <div class="card__header"><h3>En Cok Kullanilan Endpointler</h3></div>
                        <div class="card__body" id="metricsTop">Yukleniyor...</div>
                    </div>
                    <div class="card" id="metricsSlowestCard">
                        <div class="card__header"><h3>En Yavas Endpointler</h3></div>
                        <div class="card__body" id="metricsSlowest">Yukleniyor...</div>
                    </div>
                </div>
                <div class="card" style="margin-top:1rem;">
                    <div class="card__header"><h3>Log Istatistikleri</h3></div>
                    <div class="card__body" id="logStats">Yukleniyor...</div>
                </div>
            </section>`;
        await this.loadData();
    }

    async loadData() {
        try {
            const [summary, status, top, slowest, logStats] = await Promise.allSettled([
                this.api.metricsSummary(),
                this.api.metricsStatusDist(),
                this.api.metricsTopEndpoints(),
                this.api.metricsSlowest(),
                this.api.logsStats()
            ]);
            this.renderSummary(summary.status === 'fulfilled' ? summary.value : null);
            this.renderStatus(status.status === 'fulfilled' ? status.value : null);
            this.renderTop(top.status === 'fulfilled' ? top.value : null);
            this.renderSlowest(slowest.status === 'fulfilled' ? slowest.value : null);
            this.renderLogStats(logStats.status === 'fulfilled' ? logStats.value : null);
        } catch (e) {
            console.error('Metrics load error:', e);
        }
    }

    renderSummary(data) {
        const el = document.getElementById('metricsSummary');
        if (!data || data.error) { el.textContent = 'Veri alinamadi'; return; }
        el.innerHTML = `
            <div class="stat-grid">
                <div class="stat-item"><span class="stat-value">${data.total_requests || 0}</span><span class="stat-label">Toplam Istek</span></div>
                <div class="stat-item"><span class="stat-value">${(data.avg_duration_ms || 0).toFixed(1)}ms</span><span class="stat-label">Ort. Sure</span></div>
                <div class="stat-item"><span class="stat-value">${data.unique_endpoints || 0}</span><span class="stat-label">Endpoint Sayisi</span></div>
                <div class="stat-item"><span class="stat-value">${(data.error_rate || 0).toFixed(1)}%</span><span class="stat-label">Hata Orani</span></div>
            </div>`;
    }

    renderStatus(data) {
        const el = document.getElementById('metricsStatus');
        if (!data || data.error) { el.textContent = 'Veri alinamadi'; return; }
        const entries = Object.entries(data).filter(([k]) => k !== 'error');
        if (entries.length === 0) { el.textContent = 'Henuz veri yok'; return; }
        el.innerHTML = '<div class="status-bars">' + entries.map(([code, count]) => {
            const cls = code.startsWith('2') ? 'success' : code.startsWith('4') ? 'warning' : code.startsWith('5') ? 'danger' : 'info';
            return `<div class="status-bar"><span class="badge badge--${cls}">${code}</span><span class="status-count">${count}</span></div>`;
        }).join('') + '</div>';
    }

    renderTop(data) {
        const el = document.getElementById('metricsTop');
        if (!data || !data.top || data.top.length === 0) { el.textContent = 'Henuz veri yok'; return; }
        el.innerHTML = '<table class="data-table"><thead><tr><th>Endpoint</th><th>Istek</th><th>Ort. Sure</th></tr></thead><tbody>' +
            data.top.map(e => `<tr><td><code>${e.path || e.endpoint || ''}</code></td><td>${e.count || e.requests || 0}</td><td>${(e.avg_duration_ms || e.avg_ms || 0).toFixed(1)}ms</td></tr>`).join('') +
            '</tbody></table>';
    }

    renderSlowest(data) {
        const el = document.getElementById('metricsSlowest');
        if (!data || !data.slowest || data.slowest.length === 0) { el.textContent = 'Henuz veri yok'; return; }
        el.innerHTML = '<table class="data-table"><thead><tr><th>Endpoint</th><th>Ort. Sure</th><th>Istek</th></tr></thead><tbody>' +
            data.slowest.map(e => `<tr><td><code>${e.path || e.endpoint || ''}</code></td><td>${(e.avg_duration_ms || e.avg_ms || 0).toFixed(1)}ms</td><td>${e.count || e.requests || 0}</td></tr>`).join('') +
            '</tbody></table>';
    }

    renderLogStats(data) {
        const el = document.getElementById('logStats');
        if (!data || data.error) { el.textContent = 'Veri alinamadi'; return; }
        el.innerHTML = `
            <div class="stat-grid">
                <div class="stat-item"><span class="stat-value">${data.recent_in_memory || 0}</span><span class="stat-label">Bellekteki Log</span></div>
                <div class="stat-item"><span class="stat-value">${data.log_files || 0}</span><span class="stat-label">Log Dosyasi</span></div>
                <div class="stat-item"><span class="stat-value">${data.total_size_human || '0 B'}</span><span class="stat-label">Toplam Boyut</span></div>
            </div>`;
    }
}
