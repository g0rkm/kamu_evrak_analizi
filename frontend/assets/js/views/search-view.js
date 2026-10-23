import { ApiClient } from '../core/api.js';

export class SearchView {
  constructor(container) {
    this._container = container;
    this._api = new ApiClient();
  }

  async render() {
    this._container.innerHTML = `
      <div class="search-wrapper">
        <h2>Gelismis Arama</h2>
        <form id="searchForm" class="search-form">
          <input type="text" id="searchQuery" placeholder="Arama terimi..." required>
          <select id="searchPriority">
            <option value="">Tum Oncelikler</option>
            <option value="urgent">Acil</option>
            <option value="high">Yuksek</option>
            <option value="normal">Normal</option>
            <option value="low">Dusuk</option>
          </select>
          <button type="submit" class="btn btn-primary">Ara</button>
        </form>
        <div id="searchResults"><p>Arama yapin.</p></div>
      </div>`;
    this._bindEvents();
  }

  _bindEvents() {
    document.getElementById('searchForm')?.addEventListener('submit', (e) => {
      e.preventDefault();
      this._doSearch();
    });
  }

  async _doSearch() {
    const query = document.getElementById('searchQuery').value.trim();
    const priority = document.getElementById('searchPriority').value;
    const el = document.getElementById('searchResults');
    if (!query) return;
    el.innerHTML = '<p>Araniyor...</p>';
    try {
      const resp = await this._api.fullTextSearch(query);
      const data = await resp.json();
      let results = data.results || [];
      if (priority) {
        results = results.filter(r => r.priority === priority);
      }
      if (!results.length) {
        el.innerHTML = '<p>Sonuc bulunamadi.</p>';
        return;
      }
      el.innerHTML = `
        <p>${results.length} sonuc bulundu</p>
        <ul class="search-results-list">${results.map(r => `
          <li class="search-result-item">
            <strong>${r.source_name || r.id}</strong>
            <span class="badge badge-${r.priority || 'normal'}">${r.priority || 'normal'}</span>
            <p>${(r.summary || '').substring(0, 100)}...</p>
            <small>${r.created_at || ''}</small>
          </li>
        `).join('')}</ul>`;
    } catch (e) {
      el.innerHTML = '<p class="error-text">Arama hatasi.</p>';
    }
  }
}
