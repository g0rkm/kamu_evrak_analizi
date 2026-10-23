import { ApiClient } from '../core/api.js';

export class SettingsView {
  constructor(container) {
    this._container = container;
    this._api = new ApiClient();
  }

  async render() {
    this._container.innerHTML = `
      <div class="settings-wrapper">
        <h2>Sistem Ayarları ve Bilgileri</h2>
        <div id="settingsSections">
          <div class="settings-section">
            <h3>Sistem Raporu</h3>
            <div id="systemReport" class="settings-content"><p>Yükleniyor...</p></div>
          </div>
          <div class="settings-section">
            <h3>Sistem Yetenekleri</h3>
            <div id="systemCapabilities" class="settings-content"><p>Yükleniyor...</p></div>
          </div>
          <div class="settings-section">
            <h3>Yedekleme</h3>
            <div class="settings-actions">
              <button id="createBackupBtn" class="btn btn-primary">Yedek Oluştur</button>
              <button id="listBackupsBtn" class="btn btn-secondary">Yedekleri Listele</button>
            </div>
            <div id="backupResult" class="settings-content"></div>
          </div>
        </div>
      </div>`;
    this._bindEvents();
    await this._loadData();
  }

  _bindEvents() {
    document.getElementById('createBackupBtn')?.addEventListener('click', () => this._createBackup());
    document.getElementById('listBackupsBtn')?.addEventListener('click', () => this._listBackups());
  }

  async _loadData() {
    try {
      const [report, caps] = await Promise.all([
        this._api.request('/system/report'),
        this._api.request('/system/capabilities')
      ]);
      this._renderReport(report);
      this._renderCapabilities(caps);
    } catch (e) {
      const reportEl = document.getElementById('systemReport');
      if (reportEl) {
        reportEl.innerHTML = '<p class="error-text">Veriler yüklenemedi.</p>';
      }
    }
  }

  _renderReport(report) {
    const el = document.getElementById('systemReport');
    if (!el || !report) return;
    el.innerHTML = `
      <div class="info-grid">
        <div class="info-item"><strong>Versiyon:</strong> ${report.version || '-'}</div>
        <div class="info-item"><strong>Ortam:</strong> ${report.environment || '-'}</div>
        <div class="info-item"><strong>Durum:</strong> <span class="badge">${report.health?.status || '-'}</span></div>
        <div class="info-item"><strong>Çalışma Süresi:</strong> ${this._formatUptime(report.uptime_seconds)}</div>
        <div class="info-item"><strong>Toplam İstek:</strong> ${report.metrics?.total_requests || 0}</div>
        <div class="info-item"><strong>Hata Oranı:</strong> ${((report.metrics?.error_rate || 0) * 100).toFixed(1)}%</div>
      </div>`;
  }

  _renderCapabilities(caps) {
    const el = document.getElementById('systemCapabilities');
    if (!el || !caps || !caps.features) return;
    const features = Object.entries(caps.features);
    el.innerHTML = `<ul class="capability-list">${features.map(([k, v]) =>
      `<li><span class="${v ? 'active' : 'inactive'}">${v ? '✓' : '✗'}</span> ${k.replace(/_/g, ' ')}</li>`
    ).join('')}</ul>`;
  }

  async _createBackup() {
    const el = document.getElementById('backupResult');
    if (!el) return;
    try {
      const result = await this._api.request('/backup/create', { method: 'POST' });
      el.innerHTML = `<p class="success-text">Yedek oluşturuldu: ${result.file_count || 0} dosya, ${((result.size_bytes || 0) / 1024).toFixed(1)} KB</p>`;
    } catch (e) {
      el.innerHTML = '<p class="error-text">Yedek oluşturulamadı.</p>';
    }
  }

  async _listBackups() {
    const el = document.getElementById('backupResult');
    if (!el) return;
    try {
      const data = await this._api.request('/backup/list');
      if (!data.backups?.length) {
        el.innerHTML = '<p>Henüz yedek yok.</p>';
        return;
      }
      el.innerHTML = `<ul>${data.backups.map(b => `<li>${b.name} - ${((b.size_bytes || 0) / 1024).toFixed(1)} KB</li>`).join('')}</ul>`;
    } catch (e) {
      el.innerHTML = '<p class="error-text">Yedekler yüklenemedi.</p>';
    }
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
