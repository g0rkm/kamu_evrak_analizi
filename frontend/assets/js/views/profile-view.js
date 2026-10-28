import { ApiClient } from '../core/api.js';

export class ProfileView {
  constructor(container) {
    this._container = container;
    this._api = new ApiClient();
  }

  async render() {
    const token = localStorage.getItem('auth_token');
    const username = localStorage.getItem('auth_user');
    if (!token || !username) {
      this._container.innerHTML = '<div class="profile-wrapper"><p>Giris yapmadınız. <a href="#login">Giris yapın.</a></p></div>';
      return;
    }
    this._container.innerHTML = `
      <div class="profile-wrapper">
        <h2>Profil</h2>
        <div class="profile-card">
          <div class="profile-info">
            <p><strong>Kullanici:</strong> <span id="profileUser">${username}</span></p>
            <p><strong>Rol:</strong> <span id="profileRole">Yukleniyor...</span></p>
            <p><strong>Oturum:</strong> <span id="profileSession">Aktif</span></p>
          </div>
          <div class="profile-actions">
            <button id="logoutBtn" class="btn btn-secondary">Cikis Yap</button>
          </div>
        </div>
        <div class="profile-section">
          <h3>Izinler</h3>
          <div id="profilePermissions"><p>Yukleniyor...</p></div>
        </div>
      </div>`;
    this._bindEvents();
    await this._loadProfile(token);
  }

  _bindEvents() {
    document.getElementById('logoutBtn')?.addEventListener('click', () => {
      localStorage.removeItem('auth_token');
      localStorage.removeItem('auth_user');
      window.location.hash = '#login';
    });
  }

  async _loadProfile(token) {
    try {
      const resp = await this._api.validateToken(token);
      const data = resp;
      if (data.valid) {
        document.getElementById('profileRole').textContent = data.role || '-';
      }
      const rolesResp = await this._api.roles();
      const roles = rolesResp;
      const permsResp = await this._api.request('/auth/permissions');
      const perms = permsResp;
      const userRole = data.role || 'izleyici';
      const roleLevel = roles.roles?.[userRole]?.level || 0;
      const el = document.getElementById('profilePermissions');
      const entries = Object.entries(perms.permissions || {});
      el.innerHTML = `<ul class="perm-list">${entries.map(([p, level]) =>
        `<li class="${roleLevel >= level ? 'perm-granted' : 'perm-denied'}">
          <span>${roleLevel >= level ? '✓' : '✗'}</span> ${p.replace(/\./g, ' > ')}
        </li>`
      ).join('')}</ul>`;
    } catch (e) {
      document.getElementById('profileRole').textContent = 'Yuklenemedi';
    }
  }
}
