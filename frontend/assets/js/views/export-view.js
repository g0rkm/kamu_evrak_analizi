import { ApiClient } from '../core/api.js';

export class ExportView {
  constructor(container) {
    this._container = container;
    this._api = new ApiClient();
  }

  async render() {
    this._container.innerHTML = `
      <div class="export-wrapper">
        <h2>Veri Aktarimi</h2>
        <div class="export-cards">
          <div class="export-card">
            <h3>CSV Aktar</h3>
            <p>Kayitlari CSV formatinda indir</p>
            <button id="exportCsvBtn" class="btn btn-primary">CSV Indir</button>
          </div>
          <div class="export-card">
            <h3>JSON Aktar</h3>
            <p>Kayitlari JSON formatinda indir</p>
            <button id="exportJsonBtn" class="btn btn-primary">JSON Indir</button>
          </div>
          <div class="export-card">
            <h3>Ozet Rapor</h3>
            <p>Kayit istatistik raporu</p>
            <button id="exportReportBtn" class="btn btn-secondary">Rapor Goruntule</button>
          </div>
        </div>
        <div id="exportReport" style="display:none" class="export-report"></div>
      </div>`;
    this._bindEvents();
  }

  _bindEvents() {
    document.getElementById('exportCsvBtn')?.addEventListener('click', () => this._downloadCsv());
    document.getElementById('exportJsonBtn')?.addEventListener('click', () => this._downloadJson());
    document.getElementById('exportReportBtn')?.addEventListener('click', () => this._showReport());
  }

  async _downloadCsv() {
    try {
      const resp = await this._api.exportCsv();
      const blob = await resp.blob();
      this._download(blob, 'kayitlar.csv', 'text/csv');
    } catch (e) {}
  }

  async _downloadJson() {
    try {
      const resp = await this._api.exportJsonFile();
      const blob = await resp.blob();
      this._download(blob, 'kayitlar.json', 'application/json');
    } catch (e) {}
  }

  _download(blob, filename, type) {
    const url = URL.createObjectURL(new Blob([blob], { type }));
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  async _showReport() {
    const el = document.getElementById('exportReport');
    el.style.display = 'block';
    el.innerHTML = '<p>Yukleniyor...</p>';
    try {
      const resp = await this._api.exportReport();
      const data = resp;
      el.innerHTML = `
        <h3>Ozet Rapor</h3>
        <div class="report-grid">
          <div><strong>Toplam Kayit:</strong> ${data.total_records}</div>
          <div><strong>Favori:</strong> ${data.favorite_count}</div>
          <div><strong>Arsivlenmis:</strong> ${data.archived_count}</div>
        </div>
        <h4>Evrak Turu Dagilimi</h4>
        <ul>${Object.entries(data.by_document_type || {}).map(([k,v]) => `<li>${k}: ${v}</li>`).join('')}</ul>
        <h4>Oncelik Dagilimi</h4>
        <ul>${Object.entries(data.by_priority || {}).map(([k,v]) => `<li>${k}: ${v}</li>`).join('')}</ul>
        ${data.top_tags?.length ? `<h4>En Cok Kullanilan Etiketler</h4><ul>${data.top_tags.map(t => `<li>${t.tag}: ${t.count}</li>`).join('')}</ul>` : ''}`;
    } catch (e) {
      el.innerHTML = '<p class="error-text">Rapor yuklenemedi.</p>';
    }
  }
}
