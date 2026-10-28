import { ApiClient } from '../core/api.js';

export class NotificationsView {
  constructor(container) {
    this._container = container;
    this._api = new ApiClient();
  }

  async render() {
    this._container.innerHTML = `
      <div class="notif-wrapper">
        <h2>Bildirimler</h2>
        <div class="notif-actions">
          <button id="markAllReadBtn" class="btn btn-secondary">Tumunu Okundu Isaretle</button>
        </div>
        <div id="notifStats" class="notif-stats"></div>
        <div id="notifList"><p>Yukleniyor...</p></div>
      </div>`;
    this._bindEvents();
    await this._loadData();
  }

  _bindEvents() {
    document.getElementById('markAllReadBtn')?.addEventListener('click', () => this._markAllRead());
  }

  async _loadData() {
    try {
      const [notifResp, statsResp] = await Promise.all([
        this._api.notifications(100),
        this._api.notificationStats()
      ]);
      const notifs = notifResp;
      const stats = statsResp;
      this._renderStats(stats);
      this._renderList(notifs.notifications || []);
    } catch (e) {
      document.getElementById('notifList').innerHTML = '<p class="error-text">Yuklenemedi.</p>';
    }
  }

  _renderStats(stats) {
    const el = document.getElementById('notifStats');
    el.innerHTML = `<p>Toplam: ${stats.total || 0} | Okunmamis: ${stats.unread || 0}</p>`;
  }

  _renderList(notifs) {
    const el = document.getElementById('notifList');
    if (!notifs.length) { el.innerHTML = '<p>Bildirim yok.</p>'; return; }
    el.innerHTML = `<ul class="notif-list">${notifs.map(n =>
      `<li class="notif-item notif-${n.level} ${n.read ? 'read' : 'unread'}">
        <span class="notif-level">${n.level}</span>
        <strong>${n.title}</strong> - ${n.message}
        <small>${new Date(n.timestamp).toLocaleString('tr-TR')}</small>
      </li>`
    ).join('')}</ul>`;
  }

  async _markAllRead() {
    try {
      await this._api.markNotificationsRead();
      await this._loadData();
    } catch (e) {}
  }
}
