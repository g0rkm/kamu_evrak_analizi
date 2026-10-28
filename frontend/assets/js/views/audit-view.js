import { ApiClient } from '../core/api.js';

export class AuditView {
  constructor(container) {
    this._container = container;
    this._api = new ApiClient();
  }

  async render() {
    this._container.innerHTML = `
      <div class="audit-wrapper">
        <h2>Denetim Günlüğü</h2>
        <div class="audit-filters">
          <select id="auditActionFilter">
            <option value="">Tüm İşlemler</option>
            <option value="analyze">Analiz</option>
            <option value="delete">Silme</option>
            <option value="update_tags">Etiket Güncelleme</option>
            <option value="update_notes">Not Güncelleme</option>
            <option value="archive">Arşivleme</option>
            <option value="unarchive">Arşivden Çıkarma</option>
            <option value="favorite">Favori</option>
            <option value="bulk_delete">Toplu Silme</option>
            <option value="import_records">İçe Aktarma</option>
          </select>
          <button id="auditRefreshBtn" class="btn btn-sm">Yenile</button>
        </div>
        <div id="auditStats" class="audit-stats"></div>
        <table class="audit-table">
          <thead>
            <tr>
              <th>Zaman</th>
              <th>İşlem</th>
              <th>Kullanıcı</th>
              <th>Kayıt ID</th>
              <th>Detay</th>
            </tr>
          </thead>
          <tbody id="auditLogBody"></tbody>
        </table>
      </div>`;
    this._bindEvents();
    await this._loadLogs();
    await this._loadStats();
  }

  _bindEvents() {
    document.getElementById('auditRefreshBtn')?.addEventListener('click', () => this._loadLogs());
    document.getElementById('auditActionFilter')?.addEventListener('change', () => this._loadLogs());
  }

  async _loadLogs() {
    const action = document.getElementById('auditActionFilter')?.value || '';
    try {
      const params = action ? `?action=${action}` : '';
      const resp = await this._api.request(`/audit/logs${params}`);
      const data = resp;
      this._renderLogs(data.logs || []);
    } catch (e) {
      const body = document.getElementById('auditLogBody');
      if (body) body.innerHTML = '<tr><td colspan="5">Yüklenemedi</td></tr>';
    }
  }

  async _loadStats() {
    try {
      const resp = await this._api.request('/audit/stats');
      const data = resp;
      const el = document.getElementById('auditStats');
      if (el && data.total_logs !== undefined) {
        el.innerHTML = `<div class="stat-card"><strong>Toplam İşlem:</strong> ${data.total_logs}</div>`;
      }
    } catch (e) { /* silent */ }
  }

  _renderLogs(logs) {
    const body = document.getElementById('auditLogBody');
    if (!body) return;
    if (!logs.length) {
      body.innerHTML = '<tr><td colspan="5" class="empty-state">Henüz kayıt yok</td></tr>';
      return;
    }
    const sorted = [...logs].reverse();
    body.innerHTML = sorted.map(l => `
      <tr>
        <td>${l.timestamp || '-'}</td>
        <td><span class="badge">${l.action || '-'}</span></td>
        <td>${l.user || 'system'}</td>
        <td>${l.record_id || '-'}</td>
        <td>${l.details ? JSON.stringify(l.details).slice(0, 80) : '-'}</td>
      </tr>`).join('');
  }
}
