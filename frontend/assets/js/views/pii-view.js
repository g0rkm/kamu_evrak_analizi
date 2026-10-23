import { ApiClient } from '../core/api.js';

export class PiiView {
  constructor(container) {
    this._container = container;
    this._api = new ApiClient();
  }

  async render() {
    this._container.innerHTML = `
      <div class="pii-wrapper">
        <h2>Kişisel Veri (PII) Analizi</h2>
        <div class="pii-input-section">
          <textarea id="piiInputText" rows="6" placeholder="Analiz edilecek metni buraya yapıştırın..."></textarea>
          <div class="pii-actions">
            <button id="piiAnalyzeBtn" class="btn btn-primary">Analiz Et</button>
            <button id="piiMaskBtn" class="btn btn-secondary">Maskele</button>
            <button id="piiRedactBtn" class="btn btn-secondary">Redakte Et</button>
          </div>
        </div>
        <div id="piiResults" class="pii-results" style="display:none">
          <h3>Sonuçlar</h3>
          <div id="piiSummary" class="pii-summary"></div>
          <div id="piiDetails" class="pii-details"></div>
          <div id="piiOutput" class="pii-output"></div>
        </div>
      </div>`;
    this._bindEvents();
  }

  _bindEvents() {
    document.getElementById('piiAnalyzeBtn')?.addEventListener('click', () => this._analyze());
    document.getElementById('piiMaskBtn')?.addEventListener('click', () => this._mask());
    document.getElementById('piiRedactBtn')?.addEventListener('click', () => this._redact());
  }

  async _analyze() {
    const text = document.getElementById('piiInputText')?.value?.trim();
    if (!text) return;
    try {
      const data = await this._api.request('/pii/analyze', {
        method: 'POST',
        json: { text }
      });
      this._showResults(data);
    } catch (e) {
      this._showError('Analiz başarısız');
    }
  }

  async _mask() {
    const text = document.getElementById('piiInputText')?.value?.trim();
    if (!text) return;
    try {
      const data = await this._api.request('/mask-pii', {
        method: 'POST',
        json: { text }
      });
      const results = document.getElementById('piiResults');
      const output = document.getElementById('piiOutput');
      if (results) results.style.display = 'block';
      if (output) output.innerHTML = `<h4>Maskelenmiş Metin</h4><pre class="pii-masked-text">${this._escapeHtml(data.masked_text || '')}</pre><p>Tespit edilen PII sayısı: ${data.pii_count || 0}</p>`;
    } catch (e) {
      this._showError('Maskeleme başarısız');
    }
  }

  async _redact() {
    const text = document.getElementById('piiInputText')?.value?.trim();
    if (!text) return;
    try {
      const data = await this._api.request('/mask-pii', {
        method: 'POST',
        json: { text }
      });
      const results = document.getElementById('piiResults');
      const output = document.getElementById('piiOutput');
      if (results) results.style.display = 'block';
      const redacted = (data.masked_text || '').replace(/\[\*\*\*[A-Z_]+\*\*\*\]/g, '[REDACTED]');
      if (output) output.innerHTML = `<h4>Redakte Edilmiş Metin</h4><pre class="pii-masked-text">${this._escapeHtml(redacted)}</pre>`;
    } catch (e) {
      this._showError('Redaksiyon başarısız');
    }
  }

  _showResults(data) {
    const results = document.getElementById('piiResults');
    const summary = document.getElementById('piiSummary');
    const details = document.getElementById('piiDetails');
    if (results) results.style.display = 'block';
    if (summary) {
      const severity = data.severity_breakdown || {};
      summary.innerHTML = `
        <div class="pii-stat-row">
          <div class="stat-card ${data.has_critical ? 'critical' : ''}">
            <strong>Kritik:</strong> ${data.has_critical ? 'Evet' : 'Hayır'}
          </div>
          <div class="stat-card"><strong>Yüksek:</strong> ${severity.high || 0}</div>
          <div class="stat-card"><strong>Orta:</strong> ${severity.medium || 0}</div>
          <div class="stat-card"><strong>Düşük:</strong> ${severity.low || 0}</div>
        </div>`;
    }
    if (details && data.pii_types) {
      details.innerHTML = `<h4>Tespit Edilen Türler</h4><ul>${Object.entries(data.pii_types).map(([k, v]) => `<li><strong>${k}:</strong> ${v} adet</li>`).join('')}</ul>`;
    }
  }

  _showError(msg) {
    const results = document.getElementById('piiResults');
    if (results) {
      results.style.display = 'block';
      results.innerHTML = `<p class="error-text">${msg}</p>`;
    }
  }

  _escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }
}
