import { ApiClient } from '../core/api.js';
import { h, icon, replace } from '../core/dom.js';
import { fmt } from '../core/vocabulary.js';

export class NotificationsView {
    title = 'Bildirimler';

    constructor(container) {
        this._container = container;
        this._api = new ApiClient();
    }

    async render(root = this._container) {
        this.statsText = h('p', { id: 'notifStats', style: { margin: '4px 0 0', color: 'var(--color-neutral-700)' } }, 'Toplam 0 · Okunmamış 0');
        this.markBtn = h('button', { type: 'button', id: 'markAllReadBtn', class: 'btn btn-secondary', disabled: true, onClick: () => this._markAllRead() }, 'Tümünü okundu say');
        this.listRoot = h('div', { id: 'notifList' });

        const section = h('section', { style: { display: 'flex', flexDirection: 'column', gap: '24px', maxWidth: '760px', margin: '0 auto' } },
            h('div', { class: 'page-bar' },
                h('div', null, h('h1', { style: { margin: 0, fontWeight: 400 } }, 'Bildirimler'), this.statsText),
                this.markBtn),
            this.listRoot);

        replace(root, section);
        await this._loadData();
    }

    async _loadData() {
        try {
            const [notifResp, statsResp] = await Promise.all([
                this._api.notifications(100),
                this._api.notificationStats(),
            ]);
            this._renderStats(statsResp || {});
            this._renderList(notifResp?.notifications || []);
        } catch {
            replace(this.listRoot, h('p', { class: 'error-text' }, 'Bildirimler yüklenemedi.'));
        }
    }

    _renderStats(stats) {
        const total = stats.total || 0;
        const unread = stats.unread || 0;
        this.statsText.textContent = `Toplam ${total} · Okunmamış ${unread}`;
        this.markBtn.disabled = unread === 0;
    }

    _renderList(notifs) {
        if (!notifs.length) {
            replace(this.listRoot,
                h('div', { style: { textAlign: 'center', padding: '56px 0', display: 'flex', flexDirection: 'column', gap: '8px', alignItems: 'center' } },
                    h('span', { style: { width: '56px', height: '56px', borderRadius: '50%', border: '1px solid var(--color-divider)', display: 'grid', placeItems: 'center', color: 'var(--color-neutral-600)', fontSize: '22px' } },
                        icon('bell')),
                    h('div', { style: { fontFamily: 'var(--font-heading)', fontSize: '24px' } }, 'Yeni bildiriminiz yok'),
                    h('div', { style: { fontSize: '14px', color: 'var(--color-neutral-700)', maxWidth: '420px' } },
                        'Acil bir evrak geldiğinde veya bir taslak onayınızı beklediğinde size burada haber vereceğiz.')));
            return;
        }
        replace(this.listRoot, h('div', { class: 'card', style: { padding: '8px 22px' } },
            ...notifs.map((n) => h('div', {
                style: { display: 'flex', justifyContent: 'space-between', gap: '16px', padding: '14px 0', borderBottom: '1px solid var(--color-divider)', opacity: n.read ? 0.65 : 1 },
            },
                h('div', { style: { display: 'flex', flexDirection: 'column', gap: '4px' } },
                    h('div', { style: { fontSize: '15px' } }, n.title || 'Bildirim'),
                    h('div', { style: { fontSize: '13px', color: 'var(--color-neutral-700)' } }, n.message || ''),
                    h('div', { style: { fontSize: '12px', color: 'var(--color-neutral-600)' } }, fmt.date(n.timestamp))),
                h('span', { class: 'tag tag-accent', style: { alignSelf: 'center' } }, n.level || 'bilgi')))));
    }

    async _markAllRead() {
        try {
            await this._api.markNotificationsRead();
            await this._loadData();
        } catch {}
    }
}
