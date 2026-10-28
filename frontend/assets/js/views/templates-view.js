import { ApiClient } from '../core/api.js';

export class TemplatesView {
  constructor(container) {
    this._container = container;
    this._api = new ApiClient();
  }

  async render() {
    this._container.innerHTML = `
      <div class="templates-wrapper">
        <h2>Evrak Sablonlari</h2>
        <div class="templates-actions">
          <button id="addTemplateBtn" class="btn btn-primary">Yeni Sablon</button>
        </div>
        <div id="templateForm" style="display:none" class="template-form">
          <input type="text" id="tplName" placeholder="Sablon adi" required>
          <input type="text" id="tplDocType" placeholder="Evrak turu" required>
          <input type="text" id="tplDesc" placeholder="Aciklama">
          <input type="text" id="tplTags" placeholder="Etiketler (virgul ile)">
          <select id="tplPriority">
            <option value="normal">Normal</option>
            <option value="high">Yuksek</option>
            <option value="urgent">Acil</option>
            <option value="low">Dusuk</option>
          </select>
          <button id="saveTemplateBtn" class="btn btn-primary">Kaydet</button>
          <button id="cancelTemplateBtn" class="btn btn-secondary">Iptal</button>
        </div>
        <div id="templatesList"><p>Yukleniyor...</p></div>
      </div>`;
    this._bindEvents();
    await this._loadTemplates();
  }

  _bindEvents() {
    document.getElementById('addTemplateBtn')?.addEventListener('click', () => {
      document.getElementById('templateForm').style.display = 'block';
    });
    document.getElementById('cancelTemplateBtn')?.addEventListener('click', () => {
      document.getElementById('templateForm').style.display = 'none';
    });
    document.getElementById('saveTemplateBtn')?.addEventListener('click', () => this._saveTemplate());
  }

  async _loadTemplates() {
    try {
      const resp = await this._api.request('/templates');
      const data = resp;
      this._renderList(data.templates || []);
    } catch (e) {
      document.getElementById('templatesList').innerHTML = '<p class="error-text">Yuklenemedi.</p>';
    }
  }

  _renderList(templates) {
    const el = document.getElementById('templatesList');
    if (!templates.length) { el.innerHTML = '<p>Sablon yok.</p>'; return; }
    el.innerHTML = `<div class="templates-grid">${templates.map(t => `
      <div class="template-card">
        <h4>${t.name}</h4>
        <p class="template-type">${t.document_type}</p>
        <p class="template-desc">${t.description || ''}</p>
        <div class="template-meta">
          <span class="badge badge-${t.default_priority}">${t.default_priority}</span>
          ${t.builtin ? '<span class="badge">Yerlesik</span>' : `<button class="btn btn-sm btn-danger" onclick="window._deleteTemplate('${t.id}')">Sil</button>`}
        </div>
      </div>
    `).join('')}</div>`;
    window._deleteTemplate = (id) => this._deleteTemplate(id);
  }

  async _saveTemplate() {
    const name = document.getElementById('tplName').value.trim();
    const docType = document.getElementById('tplDocType').value.trim();
    if (!name || !docType) return;
    try {
      await this._api.request('/templates', {
        method: 'POST',
        json: {
          name,
          document_type: docType,
          description: document.getElementById('tplDesc').value.trim(),
          default_tags: document.getElementById('tplTags').value.split(',').map(t => t.trim()).filter(Boolean),
          default_priority: document.getElementById('tplPriority').value,
        }
      });
      document.getElementById('templateForm').style.display = 'none';
      await this._loadTemplates();
    } catch (e) {}
  }

  async _deleteTemplate(id) {
    try {
      await this._api.request(`/templates/${id}`, { method: 'DELETE' });
      await this._loadTemplates();
    } catch (e) {}
  }
}
