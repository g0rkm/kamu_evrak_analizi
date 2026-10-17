import { ApiClient } from '../core/api.js';

export class TrendsView {
  constructor(container) {
    this._container = container;
    this._chart = null;
  }

  async render() {
    this._container.innerHTML = `
      <div class="trends-wrapper">
        <h2>Analiz Trendleri</h2>
        <div class="trends-controls">
          <select id="trendsDays" class="form-select">
            <option value="7">Son 7 gün</option>
            <option value="14">Son 14 gün</option>
            <option value="30" selected>Son 30 gün</option>
            <option value="90">Son 90 gün</option>
          </select>
        </div>
        <div class="chart-container" style="position:relative;height:320px;width:100%;">
          <canvas id="trendsChart"></canvas>
        </div>
        <div id="trendsStats" class="trends-stats"></div>
      </div>
    `;

    const daysSelect = document.getElementById('trendsDays');
    daysSelect.addEventListener('change', () => this._loadTrends(parseInt(daysSelect.value)));
    await this._loadTrends(30);
  }

  async _loadTrends(days) {
    try {
      const api = new ApiClient();
      const data = await api.trends(days);
      this._renderChart(data.trends);
      this._renderStats(data.trends);
    } catch (err) {
      this._container.querySelector('.chart-container').innerHTML =
        '<p class="error-text">Trend verileri yüklenemedi.</p>';
    }
  }

  _renderChart(trends) {
    if (this._chart) {
      this._chart.destroy();
    }
    const canvas = document.getElementById('trendsChart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const labels = trends.map(t => t.date);
    const counts = trends.map(t => t.count);

    this._chart = new Chart(ctx, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          label: 'Analiz Sayısı',
          data: counts,
          borderColor: 'var(--color-primary, #2563eb)',
          backgroundColor: 'rgba(37, 99, 235, 0.1)',
          fill: true,
          tension: 0.3,
          pointRadius: 3,
          pointHoverRadius: 6,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              title: (items) => items[0]?.label || '',
              label: (item) => `${item.raw} analiz`
            }
          }
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: { maxTicksLimit: 10 }
          },
          y: {
            beginAtZero: true,
            ticks: { stepSize: 1 }
          }
        }
      }
    });
  }

  _renderStats(trends) {
    const statsEl = document.getElementById('trendsStats');
    if (!statsEl) return;
    const total = trends.reduce((s, t) => s + t.count, 0);
    const maxDay = trends.reduce((max, t) => t.count > max.count ? t : max, { count: 0 });
    const avg = trends.length > 0 ? (total / trends.length).toFixed(1) : 0;

    statsEl.innerHTML = `
      <div class="stat-card"><span class="stat-value">${total}</span><span class="stat-label">Toplam Analiz</span></div>
      <div class="stat-card"><span class="stat-value">${avg}</span><span class="stat-label">Günlük Ortalama</span></div>
      <div class="stat-card"><span class="stat-value">${maxDay.count}</span><span class="stat-label">En Yoğun Gün</span></div>
    `;
  }

  destroy() {
    if (this._chart) {
      this._chart.destroy();
      this._chart = null;
    }
  }
}
