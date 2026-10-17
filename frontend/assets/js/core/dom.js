import { icon } from './icons.js';

const PROPERTY_KEYS = new Set(['value', 'checked', 'selected', 'indeterminate']);

/**
 * Küçük, güvenli DOM oluşturucu. Metinler daima textNode olarak eklenir;
 * LLM çıktısı gibi güvenilmeyen içerik asla HTML olarak yorumlanmaz (XSS koruması).
 *
 *   h('button', { class: 'btn', onClick: fn }, icon('check'), 'Onayla')
 */
export function h(tag, props = null, ...children) {
    const el = document.createElement(tag);
    if (props) {
        for (const [key, value] of Object.entries(props)) {
            if (value == null || value === false) continue;
            if (key === 'class') el.className = value;
            else if (key === 'dataset') Object.assign(el.dataset, value);
            else if (key === 'style' && typeof value === 'object') {
                for (const [name, styleValue] of Object.entries(value)) el.style.setProperty(name.replace(/[A-Z]/g, (c) => `-${c.toLowerCase()}`), styleValue);
            }
            else if (key.startsWith('on') && typeof value === 'function') el.addEventListener(key.slice(2).toLowerCase(), value);
            else if (PROPERTY_KEYS.has(key)) el[key] = value;
            else el.setAttribute(key, value === true ? '' : String(value));
        }
    }
    append(el, children);
    return el;
}

export function append(parent, children) {
    for (const child of [children].flat(Infinity)) {
        if (child == null || child === false || child === '') continue;
        parent.append(child instanceof Node ? child : document.createTextNode(String(child)));
    }
    return parent;
}

export function replace(parent, ...children) {
    parent.replaceChildren();
    return append(parent, children);
}

export { icon };

export function emptyState({ iconName = 'info', title, text = '', compact = false, action = null }) {
    return h('div', { class: `empty${compact ? ' empty--compact' : ''}` },
        h('div', { class: 'empty__icon' }, icon(iconName)),
        title ? h('h3', null, title) : null,
        text ? h('p', null, text) : null,
        action,
    );
}

export function badge(text, variant = '', extra = '') {
    return h('span', { class: `badge ${variant ? `badge--${variant}` : ''} ${extra}`.trim() }, text);
}

export function meter(ratio, variant = '') {
    const pct = Math.round(Math.max(0, Math.min(1, ratio || 0)) * 100);
    return h('div', { class: 'meter', role: 'meter', 'aria-valuemin': 0, 'aria-valuemax': 100, 'aria-valuenow': pct },
        h('div', { class: `meter__fill ${variant ? `meter__fill--${variant}` : ''}`, style: { width: `${pct}%` } }));
}

export function scoreRing(ratio, label) {
    const pct = Math.round(Math.max(0, Math.min(1, ratio || 0)) * 100);
    const color = pct >= 80 ? 'var(--success)' : pct >= 50 ? 'var(--warning)' : 'var(--danger)';
    return h('div', { class: 'score-ring', role: 'img', 'aria-label': `${label}: yüzde ${pct}`, style: { '--value': pct, '--color': color } },
        h('span', { class: 'score-ring__value' }, `%${pct}`));
}

export function debounce(fn, wait = 300) {
    let timer;
    return (...args) => {
        clearTimeout(timer);
        timer = setTimeout(() => fn(...args), wait);
    };
}

export function downloadBlob(content, filename, type = 'application/json') {
    const url = URL.createObjectURL(new Blob([content], { type }));
    const link = h('a', { href: url, download: filename });
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export const storage = {
    get(key, fallback = null) {
        try { return localStorage.getItem(key) ?? fallback; } catch { return fallback; }
    },
    set(key, value) {
        try { localStorage.setItem(key, value); } catch { /* depolama kapalı olabilir */ }
    },
};

export function skeleton(type = 'text', count = 3) {
    const items = [];
    for (let i = 0; i < count; i++) {
        items.push(h('div', { class: `skeleton skeleton--${type}` }));
    }
    return h('div', { class: 'stack-sm', 'aria-hidden': 'true', 'aria-label': 'Yükleniyor' }, ...items);
}
