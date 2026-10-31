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
          <h2>Giriş Yap</h2>
          <form id="loginForm">
            <div class="form-group">
              <label for="username">Kullanıcı adı</label>
              <input type="text" id="username" name="username" required autocomplete="username">
            </div>
            <div class="form-group">
              <label for="password">Parola</label>
              <input type="password" id="password" name="password" required autocomplete="current-password">
            </div>
            <div id="loginError" class="error-text" style="display:none"></div>
            <button type="submit" class="btn btn-primary btn-block">Giriş</button>
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
      errEl.textContent = 'Kullanıcı adı ve parola zorunludur.';
      errEl.style.display = 'block';
      return;
    }
    try {
      const data = await this._api.request('/auth/login', {
        method: 'POST',
        json: { username, password },
      });
      if (data.error || data.detail) {
        errEl.textContent = data.detail || data.error || 'Giriş başarısız.';
        errEl.style.display = 'block';
        return;
      }
      localStorage.setItem('auth_token', data.token);
      localStorage.setItem('auth_user', JSON.stringify({ username: data.username, role: data.role || 'memur' }));
      if (this._onLogin) this._onLogin(data);
    } catch (e) {
      errEl.textContent = 'Bağlantı hatası.';
      errEl.style.display = 'block';
    }
  }
}
