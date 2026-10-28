import { ApiClient } from '../core/api.js';
import { h, icon, replace } from '../core/dom.js';
import { DRAFT_STATUS, Vocabulary, fmt } from '../core/vocabulary.js';

export class DashboardView {
    title = 'Ana sayfa';

    constructor(container) {
        this._container = container;
        this._api = new ApiClient();
    }

    async render(root = this._container) {
        const today = new Intl.DateTimeFormat('tr-TR', { day: 'numeric', month: 'long', year: 'numeric', weekday: 'long' }).format(new Date());

        this.recordsCard = h('div', { class: 'card', style: { padding: '22px', textAlign: 'center', alignItems: 'center' } },
            h('div', { class: 'card-kicker' }, 'Kayıtlı evrak'),
            h('div', { style: { fontFamily: 'var(--font-heading)', fontSize: '54px', lineHeight: 1, fontVariantNumeric: 'tabular-nums' } }, '—'),
            h('div', { style: { fontSize: '13px', color: 'var(--color-neutral-700)' } }, 'Yükleniyor…'));

        this.priorityCard = h('div', { class: 'card', style: { padding: '22px' } },
            h('div', { class: 'card-kicker', style: { textAlign: 'center' } }, 'Öncelik durumu'),
            h('div', { style: { fontSize: '13px', color: 'var(--color-neutral-700)', textAlign: 'center' } }, 'Yükleniyor…'));

        this.notifCard = h('div', { class: 'card', style: { padding: '22px', textAlign: 'center', alignItems: 'center' } },
            h('div', { class: 'card-kicker' }, 'Okunmamış bildirim'),
            h('div', { style: { fontFamily: 'var(--font-heading)', fontSize: '54px', lineHeight: 1, fontVariantNumeric: 'tabular-nums' } }, '—'),
            h('div', { style: { fontSize: '13px', color: 'var(--color-neutral-700)' } }, 'Yükleniyor…'));

        this.systemCard = h('div', { class: 'card', style: { padding: '22px', textAlign: 'center', alignItems: 'center' } },
            h('div', { class: 'card-kicker' }, 'Sistem'),
            h('div', { style: { fontFamily: 'var(--font-heading)', fontSize: '30px', lineHeight: 1.1, paddingTop: '10px' } }, '—'),
            h('div', { style: { fontSize: '13px', color: 'var(--color-neutral-700)' } }, 'Kontrol ediliyor…'));

        this.recentRecordsList = h('div', null,
            h('div', { style: { padding: '28px 0', textAlign: 'center', color: 'var(--color-neutral-700)', fontSize: '14px' } }, 'Yükleniyor…'));
        this.recentNotifsList = h('div', null,
            h('div', { style: { padding: '28px 0', textAlign: 'center', color: 'var(--color-neutral-700)', fontSize: '14px' } }, 'Yükleniyor…'));

        const section = h('section', { style: { display: 'flex', flexDirection: 'column', gap: '36px' } },
            h('div', { style: { textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '10px', padding: '12px 0 4px' } },
                h('div', { class: 'card-kicker' }, today),
                h('h1', { style: { fontWeight: 400, fontSize: '46px', margin: 0 } }, 'Hoş geldiniz'),
                h('p', { style: { maxWidth: '560px', margin: 0, color: 'var(--color-neutral-700)', fontSize: '16px', textWrap: 'pretty' } },
                    'Bir evrak yükleyin; sistem türünü, önceliğini ve ilgili birimi belirleyip size bir cevap yazısı taslağı hazırlasın.'),
                h('div', { style: { display: 'flex', gap: '12px', marginTop: '12px', flexWrap: 'wrap', justifyContent: 'center' } },
                    h('a', { class: 'btn btn-primary', href: '#/analiz', style: { fontSize: '17px', padding: '12px 26px' } },
                        icon('upload'), 'Yeni evrak analiz et'),
                    h('a', { class: 'btn btn-secondary', href: '#/gecmis', style: { fontSize: '17px', padding: '12px 26px' } },
                        'Geçmiş evraklarım'))),
            h('div', { style: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '18px' } },
                this.recordsCard, this.priorityCard, this.notifCard, this.systemCard),
            h('div', { style: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '28px' } },
                h('div', { style: { display: 'flex', flexDirection: 'column', gap: '10px' } },
                    h('div', { class: 'section-head' },
                        h('h3', { style: { margin: 0 } }, 'Son incelenen evraklar'),
                        h('a', { href: '#/gecmis', style: { fontSize: '13px' } }, 'Tümünü gör')),
                    this.recentRecordsList),
                h('div', { style: { display: 'flex', flexDirection: 'column', gap: '10px' } },
                    h('div', { class: 'section-head' },
                        h('h3', { style: { margin: 0 } }, 'Son bildirimler'),
                        h('a', { href: '#notifications', style: { fontSize: '13px' } }, 'Bildirimlere git')),
                    this.recentNotifsList)));

        replace(root, section);
        await this._loadData();
    }

    async _loadData() {
        const [summary, notifs, recent, health, meta] = await Promise.allSettled([
            this._api.request('/dashboard/summary'),
            this._api.request('/notifications?limit=5'),
            this._api.history({ limit: 5 }),
            this._api.health(),
            this._api.meta(),
        ]);
        const vocab = new Vocabulary(meta.status === 'fulfilled' ? meta.value : undefined);
        if (summary.status === 'fulfilled') this._renderCards(summary.value, health.status === 'fulfilled' ? health.value : null);
        else replace(this.recordsCard, h('div', { class: 'card-kicker' }, 'Kayıtlı evrak'), h('p', { class: 'error-text', style: { margin: 0 } }, 'Veri yüklenemedi'));

        this._renderRecentRecords(recent.status === 'fulfilled' ? (recent.value.items || []) : [], vocab);
        this._renderNotifications(notifs.status === 'fulfilled' ? (notifs.value.notifications || []) : []);
    }

    _renderCards(s, health) {
        const active = s.active_records ?? 0;
        const archived = s.archived_records ?? 0;
        const deleted = s.deleted_records ?? 0;
        replace(this.recordsCard,
            h('div', { class: 'card-kicker' }, 'Kayıtlı evrak'),
            h('div', { style: { fontFamily: 'var(--font-heading)', fontSize: '54px', lineHeight: 1, fontVariantNumeric: 'tabular-nums' } }, fmt.number(active)),
            h('div', { style: { fontSize: '13px', color: 'var(--color-neutral-700)' } }, `${active} aktif · ${archived} arşivde · ${deleted} silinen`));

        const pd = s.priority_distribution || {};
        const rows = [
            ['Acil', (pd.urgent || 0) + (pd.acil || 0)],
            ['Yüksek', (pd.high || 0) + (pd.yuksek || 0)],
            ['Normal', pd.normal || 0],
            ['Düşük', (pd.low || 0) + (pd.dusuk || 0)],
        ];
        const total = Math.max(1, rows.reduce((sum, [, n]) => sum + n, 0));
        replace(this.priorityCard,
            h('div', { class: 'card-kicker', style: { textAlign: 'center' } }, 'Öncelik durumu'),
            ...rows.map(([label, n]) => h('div', { class: 'bar-row' },
                h('span', null, label),
                h('span', { class: 'meter' }, h('span', { class: 'meter__fill', style: { display: 'block', width: `${Math.round((n / total) * 100)}%` } })),
                h('span', { class: 'bar-row__value' }, String(n)))));

        const unread = s.unread_notifications ?? 0;
        replace(this.notifCard,
            h('div', { class: 'card-kicker' }, 'Okunmamış bildirim'),
            h('div', { style: { fontFamily: 'var(--font-heading)', fontSize: '54px', lineHeight: 1, fontVariantNumeric: 'tabular-nums' } }, fmt.number(unread)),
            h('div', { style: { fontSize: '13px', color: 'var(--color-neutral-700)' } }, unread ? 'Okunmamış uyarınız var' : 'Yeni bir uyarınız yok'));

        const llmOk = health ? health.llm_configured !== false : true;
        replace(this.systemCard,
            h('div', { class: 'card-kicker' }, 'Sistem'),
            h('div', { style: { fontFamily: 'var(--font-heading)', fontSize: '30px', lineHeight: 1.1, paddingTop: '10px' } }, llmOk ? 'Çalışıyor' : 'Kontrol gerekli'),
            h('div', { style: { fontSize: '13px', color: 'var(--color-neutral-700)' } },
                llmOk ? 'Her şey yolunda, analiz yapabilirsiniz' : 'Yapay zekâ servisi yapılandırılmamış'));
    }

    _renderRecentRecords(items, vocab) {
        if (!items.length) {
            replace(this.recentRecordsList,
                h('div', { style: { padding: '28px 0', textAlign: 'center', color: 'var(--color-neutral-700)', fontSize: '14px' } },
                    'Henüz incelenmiş evrak yok. İlk evrakınızı analiz ettiğinizde burada görünür.'));
            return;
        }
        replace(this.recentRecordsList, ...items.map((r) => {
            const status = DRAFT_STATUS[r.draft_status] || DRAFT_STATUS.pending;
            return h('a', {
                href: `#/analiz/${encodeURIComponent(r.id)}`,
                style: { display: 'flex', justifyContent: 'space-between', gap: '16px', padding: '12px 0', borderBottom: '1px solid var(--color-divider)', textDecoration: 'none', color: 'var(--color-text)' },
            },
                h('div', { style: { display: 'flex', flexDirection: 'column', gap: '2px', minWidth: 0 } },
                    h('span', { style: { fontSize: '15px', overflowWrap: 'anywhere' } }, r.source_name || 'Adsız evrak'),
                    h('span', { style: { fontSize: '12px', color: 'var(--color-neutral-700)' } }, `${vocab.documentType(r.document_type)} · ${fmt.relativeTime(r.timestamp)}`)),
                h('span', { class: 'tag tag-accent', style: { alignSelf: 'center', whiteSpace: 'nowrap' } }, status.label));
        }));
    }

    _renderNotifications(notifs) {
        if (!notifs.length) {
            replace(this.recentNotifsList,
                h('div', { style: { padding: '28px 0', textAlign: 'center', color: 'var(--color-neutral-700)', fontSize: '14px' } },
                    'Henüz bildiriminiz yok. Onay bekleyen bir taslak olduğunda burada görünür.'));
            return;
        }
        replace(this.recentNotifsList, ...notifs.map((n) => h('div', {
            style: { display: 'flex', justifyContent: 'space-between', gap: '16px', padding: '12px 0', borderBottom: '1px solid var(--color-divider)' },
        },
            h('div', { style: { display: 'flex', flexDirection: 'column', gap: '2px', minWidth: 0 } },
                h('span', { style: { fontSize: '15px' } }, n.title || 'Bildirim'),
                h('span', { style: { fontSize: '12px', color: 'var(--color-neutral-700)' } }, `${n.message || ''} · ${fmt.relativeTime(n.timestamp)}`)),
            h('span', { class: 'tag tag-neutral', style: { alignSelf: 'center', whiteSpace: 'nowrap' } }, n.level || 'bilgi'))));
    }
}
