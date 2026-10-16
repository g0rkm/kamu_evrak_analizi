import { h, icon, storage } from './dom.js';

/** Sağ altta beliren, kendiliğinden kapanan bildirimler. */
export class Toaster {
    static ICONS = { success: 'circleCheck', error: 'circleX', info: 'info' };

    constructor(root) {
        this.root = root;
    }

    show(message, type = 'info', timeout = type === 'error' ? 7000 : 4000) {
        const close = h('button', { type: 'button', class: 'btn btn--ghost btn--icon btn--sm', 'aria-label': 'Bildirimi kapat' }, icon('x'));
        const toast = h('div', { class: `toast toast--${type}`, role: type === 'error' ? 'alert' : 'status' },
            h('span', { class: 'toast__icon' }, icon(Toaster.ICONS[type] || 'info')),
            h('div', { class: 'toast__message' }, message),
            close,
        );
        const dismiss = () => {
            toast.classList.add('is-leaving');
            setTimeout(() => toast.remove(), 200);
        };
        close.addEventListener('click', dismiss);
        this.root.append(toast);
        if (timeout) setTimeout(dismiss, timeout);
    }

    success(message) { this.show(message, 'success'); }
    error(message) { this.show(message, 'error'); }
    info(message) { this.show(message, 'info'); }
}

/** Açık/koyu tema tercihi. Tercih, ilk boyamadan önce index.html'deki betikle uygulanır. */
export class ThemeController {
    constructor(button) {
        this.button = button;
        this.button.addEventListener('click', () => this.toggle());
        this.render();
    }

    get current() {
        return document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
    }

    toggle() {
        const next = this.current === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', next);
        storage.set('theme', next);
        this.render();
    }

    render() {
        const dark = this.current === 'dark';
        this.button.replaceChildren(icon(dark ? 'sun' : 'moon'));
        this.button.setAttribute('aria-label', dark ? 'Açık temaya geç' : 'Koyu temaya geç');
        this.button.title = this.button.getAttribute('aria-label');
    }
}

/** Yerel <dialog> tabanlı onay penceresi. `await confirmDialog({...})` → true/false */
export function confirmDialog({ title, message, confirmText = 'Onayla', cancelText = 'Vazgeç', danger = false }) {
    return new Promise((resolve) => {
        const confirmBtn = h('button', { type: 'button', class: `btn ${danger ? 'btn--danger' : 'btn--primary'}` }, confirmText);
        const cancelBtn = h('button', { type: 'button', class: 'btn btn--secondary' }, cancelText);
        const dialog = h('dialog', { class: 'dialog', 'aria-labelledby': 'dialogTitle' },
            h('div', { class: 'dialog__body' }, h('h2', { id: 'dialogTitle' }, title), h('p', { class: 'muted' }, message)),
            h('div', { class: 'dialog__footer' }, cancelBtn, confirmBtn),
        );
        const finish = (result) => {
            dialog.close();
            dialog.remove();
            resolve(result);
        };
        confirmBtn.addEventListener('click', () => finish(true));
        cancelBtn.addEventListener('click', () => finish(false));
        dialog.addEventListener('cancel', (event) => { event.preventDefault(); finish(false); });
        document.body.append(dialog);
        dialog.showModal();
        cancelBtn.focus();
    });
}

/**
 * Erişilebilir sekme bileşeni (WAI-ARIA tabs deseni: ok tuşları, Home/End).
 * tabs: [{ id, label, icon, count?, countVariant?, render: () => Node }]
 */
export class Tabs {
    constructor(tabs, { initial, onChange } = {}) {
        this.tabs = tabs;
        this.onChange = onChange;
        this.list = h('div', { class: 'tabs', role: 'tablist', 'aria-label': 'Analiz sonuçları' });
        this.panel = h('div', { class: 'tab-panel', role: 'tabpanel', tabindex: 0 });
        this.buttons = tabs.map((tab, index) => {
            const button = h('button', {
                type: 'button', class: 'tab', role: 'tab', id: `tab-${tab.id}`,
                'aria-controls': 'tabPanel', 'aria-selected': 'false', tabindex: -1,
                onClick: () => this.select(tab.id),
                onKeydown: (event) => this.onKeydown(event, index),
            }, icon(tab.icon), tab.label, tab.count ? h('span', { class: `count ${tab.countVariant ? `count--${tab.countVariant}` : ''}` }, tab.count) : null);
            this.list.append(button);
            return button;
        });
        this.panel.id = 'tabPanel';
        this.element = h('div', null, this.list, this.panel);
        this.select(tabs.some((t) => t.id === initial) ? initial : tabs[0].id, false);
    }

    select(id, focus = false) {
        const index = this.tabs.findIndex((t) => t.id === id);
        if (index < 0) return;
        this.buttons.forEach((button, i) => {
            const active = i === index;
            button.setAttribute('aria-selected', String(active));
            button.tabIndex = active ? 0 : -1;
        });
        this.panel.setAttribute('aria-labelledby', `tab-${id}`);
        this.panel.replaceChildren(this.tabs[index].render());
        if (focus) this.buttons[index].focus();
        this.current = id;
        this.onChange?.(id);
    }

    onKeydown(event, index) {
        const last = this.tabs.length - 1;
        const target = { ArrowRight: index === last ? 0 : index + 1, ArrowLeft: index === 0 ? last : index - 1, Home: 0, End: last }[event.key];
        if (target === undefined) return;
        event.preventDefault();
        this.select(this.tabs[target].id, true);
    }
}
