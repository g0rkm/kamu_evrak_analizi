import { ApiClient } from '../core/api.js';

export class DashboardView {
  constructor(container) {
    this._container = container;
    this._api = new ApiClient();
  }

  async render() {
    this._container.innerHTML = `
      <div class="dashboard-wrapper">
        <h2>Kontrol Paneli</h2>
        <div id="dashboardCards" class="dashboard-grid">
          <div class="dash-card" id="cardRecords"><h3>Kayitlar</h3><p>Yukleniyor...</p></div>
          <div class="dash-card" id="cardPriority"><h3>Oncelik Dagilimi</h3><p>Yukleniyor...</p></div>
          <div class="dash-card" id="cardNotifications"><h3>Bildirimler</h3><p>Yukleniyor...</p></div>
          <div class="dash-card" id="cardSystem"><h3>Sistem</h3><p>Yukleniyor...</p></div>
        </div>
        <div class="dashboard-section">
          <h3>Son Bildirimler</h3>
          <div id="recentNotifications"><p>Yukleniyor...</p></div>
        </div>
      </div>`;
    await this._loadData();
  }

  async _loadData() {
    try {
      const [summaryResp, notifResp] = await Promise.all([
        this._api.request('/dashboard/summary'),
        this._api.request('/notifications?limit=5')
      ]);
      const summary = summaryResp;
      const notifs = notifResp;
      this._renderCards(summary);
      this._renderNotifications(notifs.notifications || []);
    } catch (e) {
      document.getElementById('cardRecords').innerHTML = '<h3>Kayitlar</h3><p class="error-text">Veri yuklenemedi</p>';
    }
  }

  _renderCards(s) {
    document.getElementById('cardRecords').innerHTML = `
      <h3>Kayitlar</h3>
      <div class="dash-stat">${s.active_records || 0}</div>
      <div class="dash-detail">Aktif: ${s.active_records || 0} | Arsiv: ${s.archived_records || 0} | Silinen: ${s.deleted_records || 0}</div>`;

    const pd = s.priority_distribution || {};
    document.getElementById('cardPriority').innerHTML = `
      <h3>Oncelik Dagilimi</h3>
      <div class="priority-bars">
        ${['urgent','high','normal','low'].map(p =>
          `<div class="pbar"><span class="pbar-label ${p}">${p}</span><span class="pbar-count">${pd[p] || 0}</span></div>`
        ).join('')}
      </div>`;

    document.getElementById('cardNotifications').innerHTML = `
      <h3>Bildirimler</h3>
      <div class="dash-stat">${s.unread_notifications || 0}</div>
      <div class="dash-detail">Okunmamis bildirim</div>`;

    document.getElementById('cardSystem').innerHTML = `
      <h3>Sistem</h3>
      <div class="dash-detail">Calisma: ${this._formatUptime(s.uptime_seconds)}</div>
      <div class="dash-detail">Denetim kaydi: ${s.audit_log_count || 0}</div>`;
  }

  _renderNotifications(notifs) {
    const el = document.getElementById('recentNotifications');
    if (!notifs.length) { el.innerHTML = '<p>Bildirim yok.</p>'; return; }
    el.innerHTML = `<ul class="notif-list">${notifs.map(n =>
      `<li class="notif-item notif-${n.level}">
        <span class="notif-level">${n.level}</span>
        <strong>${n.title}</strong> - ${n.message}
        <small>${new Date(n.timestamp).toLocaleString('tr-TR')}</small>
      </li>`
    ).join('')}</ul>`;
  }

  _formatUptime(seconds) {
    if (!seconds) return '-';
    if (seconds < 60) return Math.round(seconds) + 's';
    if (seconds < 3600) return Math.round(seconds / 60) + 'dk';
    const h = Math.floor(seconds / 3600);
    const m = Math.round((seconds % 3600) / 60);
    return h + 'sa ' + m + 'dk';
  }
}
