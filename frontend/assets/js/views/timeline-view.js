import { ApiClient } from '../core/api.js';

export class TimelineView {
  constructor(container) {
    this._container = container;
    this._api = new ApiClient();
  }

  async render() {
    this._container.innerHTML = `
      <div class="timeline-wrapper">
        <h2>Zaman Çizelgesi</h2>
        <div class="timeline-controls">
          <input type="date" id="timelineStart" />
          <input type="date" id="timelineEnd" />
          <button id="timelineLoadBtn" class="btn btn-sm">Yükle</button>
        </div>
        <div id="timelineContent" class="timeline"></div>
      </div>`;
    this._bindEvents();
    await this._loadTimeline();
  }

  _bindEvents() {
    document.getElementById('timelineLoadBtn')?.addEventListener('click', () => this._loadTimeline());
  }

  async _loadTimeline() {
    const startEl = document.getElementById('timelineStart');
    const endEl = document.getElementById('timelineEnd');
    let url = '/history/timeline';
    const params = [];
    if (startEl?.value) params.push('start_date=' + startEl.value);
    if (endEl?.value) params.push('end_date=' + endEl.value);
    if (params.length) url += '?' + params.join('&');

    try {
      const resp = await this._api.request(url);
      const data = resp;
      this._renderTimeline(data.timeline || data.records || []);
    } catch (e) {
      document.getElementById('timelineContent').innerHTML = '<p class="error-text">Zaman çizelgesi yüklenemedi.</p>';
    }
  }

  _renderTimeline(items) {
    const el = document.getElementById('timelineContent');
    if (!el) return;
    if (!items.length) {
      el.innerHTML = '<p class="empty-state">Bu aralıkta kayıt bulunamadı.</p>';
      return;
    }
    el.innerHTML = items.map(item => `
      <div class="timeline-item">
        <div class="timeline-marker"></div>
        <div class="timeline-body">
          <div class="timeline-date">${item.timestamp || item.date || '-'}</div>
          <div class="timeline-title">${item.source_name || item.file_name || 'Belge'}</div>
          <div class="timeline-meta">
            <span class="badge">${item.document_type || '-'}</span>
            ${item.confidence_score ? '<span>Güven: %' + (item.confidence_score * 100).toFixed(0) + '</span>' : ''}
          </div>
        </div>
      </div>`).join('');
  }
}
