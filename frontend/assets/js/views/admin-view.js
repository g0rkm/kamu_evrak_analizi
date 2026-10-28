export default class AdminView {
    constructor(api) {
        this.api = api;
    }

    async render(container) {
        container.innerHTML = `
            <section class="view-section">
                <h1>Yönetim Paneli</h1>
                <div class="metrics-grid">
                    <div class="card">
                        <div class="card__header"><h3>Bakım Modu</h3></div>
                        <div class="card__body" id="maintenancePanel">Yükleniyor...</div>
                    </div>
                    <div class="card">
                        <div class="card__header"><h3>Servis Durumu</h3></div>
                        <div class="card__body" id="serviceStatus">Yükleniyor...</div>
                    </div>
                    <div class="card">
                        <div class="card__header"><h3>Sistem Bilgisi</h3></div>
                        <div class="card__body" id="systemInfo">Yükleniyor...</div>
                    </div>
                    <div class="card">
                        <div class="card__header"><h3>Son Loglar</h3></div>
                        <div class="card__body" id="recentLogs">Yükleniyor...</div>
                    </div>
                </div>
                <div class="card" style="margin-top:1.5rem">
                  <h3>Performans Profiler</h3>
                  <div id="profiler-stats" class="stat-grid">Yükleniyor...</div>
                </div>
                <div class="card" style="margin-top:1.5rem">
                  <h3>Girdi Dogrulama</h3>
                  <div style="display:flex;gap:0.5rem;margin-bottom:1rem">
                    <input type="text" id="validate-input" placeholder="Metin girin..." style="flex:1;padding:0.5rem;border:1px solid var(--border);border-radius:4px">
                    <button id="btn-validate" class="btn btn-primary">Dogrula</button>
                  </div>
                  <div id="validate-result" style="display:none;padding:1rem;border-radius:4px"></div>
                </div>
            </section>`;
        await this.loadData();
    }

    async loadData() {
        try {
            const [maint, config, uptime, logs] = await Promise.allSettled([
                this.api.request('/maintenance/status'),
                this.api.request('/system/config-report'),
                this.api.request('/system/uptime'),
                this.api.logsRecent()
            ]);
            this.renderMaintenance(maint.status === 'fulfilled' ? maint.value : null);
            this.renderServices(config.status === 'fulfilled' ? config.value : null);
            this.renderSystemInfo(uptime.status === 'fulfilled' ? uptime.value : null);
            this.renderLogs(logs.status === 'fulfilled' ? logs.value : null);

            try {
              const profilerResp = await fetch('/api/profiler/summary');
              const profilerData = profilerResp;
              const profilerEl = document.getElementById('profiler-stats');
              if (profilerEl) {
                profilerEl.innerHTML = `
                  <div class="stat-item"><span class="stat-value">${profilerData.total_profiled || 0}</span><span class="stat-label">Toplam İstek</span></div>
                  <div class="stat-item"><span class="stat-value">${profilerData.unique_endpoints || 0}</span><span class="stat-label">Endpoint</span></div>
                  <div class="stat-item"><span class="stat-value">${profilerData.slow_requests_count || 0}</span><span class="stat-label">Yavas Istek</span></div>
                  <div class="stat-item"><span class="stat-value">${profilerData.global_avg_ms || 0}ms</span><span class="stat-label">Ort. Süre</span></div>
                `;
              }
            } catch(e) { console.error('Profiler verisi alinamadi:', e); }

            const btnValidate = document.getElementById('btn-validate');
            if (btnValidate) {
              btnValidate.addEventListener('click', async () => {
                const input = document.getElementById('validate-input').value;
                const resultEl = document.getElementById('validate-result');
                try {
                  const resp = await fetch('/api/sanitize/check', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({text: input})
                  });
                  const data = resp;
                  resultEl.style.display = 'block';
                  if (data.safe) {
                    resultEl.style.background = '#d4edda';
                    resultEl.style.color = '#155724';
                    resultEl.textContent = 'Guvenli girdi';
                  } else {
                    resultEl.style.background = '#f8d7da';
                    resultEl.style.color = '#721c24';
                    resultEl.innerHTML = 'Tehdit tespit edildi:<br>' + data.threats.map(t => '- ' + t).join('<br>');
                  }
                } catch(e) {
                  resultEl.style.display = 'block';
                  resultEl.style.background = '#fff3cd';
                  resultEl.textContent = 'Dogrulama hatasi: ' + e.message;
                }
              });
            }
        } catch (e) {
            console.error('Admin load error:', e);
        }
    }

    renderMaintenance(data) {
        const el = document.getElementById('maintenancePanel');
        if (!data) { el.textContent = 'Veri alinamadi'; return; }
        const active = data.maintenance_mode;
        el.innerHTML = `
            <div style="margin-bottom:1rem;">
                <span class="badge badge--${active ? 'danger' : 'success'}">${active ? 'AKTIF' : 'KAPALI'}</span>
                ${data.reason ? `<p style="margin-top:0.5rem;">${data.reason}</p>` : ''}
            </div>
            <div style="display:flex;gap:0.5rem;">
                <button class="btn btn--sm ${active ? 'btn--ghost' : 'btn--primary'}" id="btnMaintenanceToggle">
                    ${active ? 'Bakımı Kapat' : 'Bakım Modunu Aç'}
                </button>
            </div>`;
        document.getElementById('btnMaintenanceToggle').addEventListener('click', async () => {
            if (active) {
                await this.api.request('/maintenance/disable', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
            } else {
                const reason = prompt('Bakım nedeni:') || '';
                await this.api.request('/maintenance/enable', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ reason }) });
            }
            await this.loadData();
        });
    }

    renderServices(data) {
        const el = document.getElementById('serviceStatus');
        if (!data || !data.services) { el.textContent = 'Veri alinamadi'; return; }
        el.innerHTML = '<div class="stat-grid" style="grid-template-columns:repeat(auto-fit,minmax(140px,1fr));">' +
            Object.entries(data.services).map(([name, active]) =>
                `<div class="stat-item"><span class="badge badge--${active ? 'success' : 'warning'}">${active ? 'Aktif' : 'Pasif'}</span><span class="stat-label">${name}</span></div>`
            ).join('') + '</div>';
    }

    renderSystemInfo(data) {
        const el = document.getElementById('systemInfo');
        if (!data) { el.textContent = 'Veri alinamadi'; return; }
        el.innerHTML = `
            <div class="stat-grid">
                <div class="stat-item"><span class="stat-value">${data.uptime_human || '-'}</span><span class="stat-label">Calisma Suresi</span></div>
                <div class="stat-item"><span class="stat-value">${(data.uptime_seconds || 0).toFixed(0)}s</span><span class="stat-label">Saniye</span></div>
            </div>`;
    }

    renderLogs(data) {
        const el = document.getElementById('recentLogs');
        if (!data || !data.logs) { el.textContent = 'Henuz log yok'; return; }
        if (data.logs.length === 0) { el.textContent = 'Henuz log yok'; return; }
        el.innerHTML = '<div style="max-height:300px;overflow-y:auto;font-size:0.85rem;">' +
            data.logs.slice(-20).reverse().map(log => {
                const cls = log.level === 'ERROR' ? 'danger' : log.level === 'WARNING' ? 'warning' : 'info';
                return `<div style="padding:0.25rem 0;border-bottom:1px solid var(--clr-border);"><span class="badge badge--${cls}" style="font-size:0.7rem;">${log.level}</span> <span style="color:var(--clr-text-muted);">${log.timestamp?.substring(11,19) || ''}</span> ${log.message}</div>`;
            }).join('') + '</div>';
    }
}
