import { ApiClient } from '../core/api.js';

export class LoginView {
  constructor(container, onLogin) {
    this._container = container;
    this._api = new ApiClient();
    this._onLogin = onLogin;
  }

  async render() {
    this._container.innerHTML = `
      <div class="login-wrapper">
        <div class="login-card">
          <h2>Giris Yap</h2>
          <form id="loginForm">
            <div class="form-group">
              <label for="username">Kullanici Adi</label>
              <input type="text" id="username" name="username" required autocomplete="username">
            </div>
            <div class="form-group">
              <label for="password">Parola</label>
              <input type="password" id="password" name="password" required autocomplete="current-password">
            </div>
            <div id="loginError" class="error-text" style="display:none"></div>
            <button type="submit" class="btn btn-primary btn-block">Giris</button>
          </form>
        </div>
      </div>`;
    this._bindEvents();
  }

  _bindEvents() {
    document.getElementById('loginForm')?.addEventListener('submit', (e) => {
      e.preventDefault();
      this._handleLogin();
    });
  }

  async _handleLogin() {
    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value;
    const errEl = document.getElementById('loginError');
    errEl.style.display = 'none';
    if (!username || !password) {
      errEl.textContent = 'Kullanici adi ve parola zorunludur.';
      errEl.style.display = 'block';
      return;
    }
    try {
      const resp = await this._api.request('/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
      });
      if (!resp.ok) {
        const data = await resp.json();
        errEl.textContent = data.detail || 'Giris basarisiz.';
        errEl.style.display = 'block';
        return;
      }
      const data = await resp.json();
      localStorage.setItem('auth_token', data.token);
      localStorage.setItem('auth_user', data.username);
      if (this._onLogin) this._onLogin(data);
    } catch (e) {
      errEl.textContent = 'Baglanti hatasi.';
      errEl.style.display = 'block';
    }
  }
}
