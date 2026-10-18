import { ApiClient } from '../core/api.js';

export class DashboardView {
  constructor(container) {
    this._container = container;
    this._api = new ApiClient();
  }

  async render() {
    this._container.innerHTML = '<div class="dashboard-grid" id="dashboardGrid"><p>Yükleniyor...</p></div>';
    try {
      const summary = await this._api.systemSummary();
      this._renderCards(summary);
    } catch (err) {
      this._container.innerHTML = '<p class="error-text">Dashboard verileri yüklenemedi.</p>';
    }
  }

  _renderCards(data) {
    const grid = document.getElementById('dashboardGrid');
    if (!grid) return;
    const cards = [
      { title: 'Toplam Analiz', value: data.total_analyses, subtitle: 'tüm zamanlar' },
      { title: 'Ortalama Güven', value: (data.avg_confidence * 100).toFixed(0) + '%', subtitle: 'confidence score' },
      { title: 'Favoriler', value: data.favorites_count, subtitle: 'işaretlenen kayıtlar' },
      { title: 'Toplam İstek', value: data.total_requests, subtitle: 'API istekleri' },
      { title: 'Hata Oranı', value: (data.error_rate * 100).toFixed(1) + '%', subtitle: 'son dönem' },
      { title: 'Çalışma Süresi', value: this._formatUptime(data.uptime_seconds), subtitle: 'uptime' },
    ];
    grid.innerHTML = cards.map(c => `
      <div class="dashboard-card">
        <h3>${c.title}</h3>
        <div class="value">${c.value}</div>
        <div class="subtitle">${c.subtitle}</div>
      </div>
    `).join('');
  }

  _formatUptime(seconds) {
    if (seconds < 60) return Math.round(seconds) + 's';
    if (seconds < 3600) return Math.round(seconds / 60) + 'dk';
    const h = Math.floor(seconds / 3600);
    const m = Math.round((seconds % 3600) / 60);
    return h + 'sa ' + m + 'dk';
  }
}
