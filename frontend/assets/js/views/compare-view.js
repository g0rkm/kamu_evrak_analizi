import { emptyState, h, icon, replace, scoreRing } from '../core/dom.js';
import { fmt } from '../core/vocabulary.js';

export class CompareView {
    title = 'Karşılaştır';

    constructor({ api, vocab, toaster }) {
        this.api = api;
        this.vocab = vocab;
        this.toaster = toaster;
        this.element = this.build();
    }

    textField(id, label) {
        const counter = h('span', { class: 'field__hint' });
        const textarea = h('textarea', {
            class: 'textarea', id, placeholder: 'Evrak metnini yapıştırın…',
            onInput: () => { counter.textContent = `${fmt.number(textarea.value.trim().length)} karakter`; },
            onKeydown: (e) => { if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); this.submit(); } },
        });
        counter.textContent = '0 karakter';
        return { textarea, element: h('div', { class: 'field' }, h('label', { class: 'field__label', for: id }, label), textarea, counter) };
    }

    build() {
        this.first = this.textField('compareFirst', 'Birinci evrak');
        this.second = this.textField('compareSecond', 'İkinci evrak');
        this.error = h('p', { class: 'field__error', role: 'alert', hidden: true });
        this.button = h('button', { type: 'button', class: 'btn btn--primary btn--lg', onClick: () => this.submit() }, icon('compare'), 'Karşılaştır');
        this.resultRoot = h('div', { 'aria-live': 'polite' });

        return h('div', { class: 'stack' },
            h('div', { class: 'view-header' },
                h('div', null, h('h1', null, 'Evrak karşılaştırma'), h('p', null, 'İki evrak arasındaki benzerlikleri, farkları ve ortak temaları görün.'))),
            h('section', { class: 'card card__body stack' },
                h('div', { class: 'compare-grid' }, this.first.element, this.second.element),
                h('div', { class: 'row', style: { justifyContent: 'center' } },
                    h('button', { type: 'button', class: 'btn btn--ghost btn--sm', onClick: () => this.swap(), title: 'Metinleri yer değiştir' }, icon('refresh'), 'Yer değiştir')),
                this.error,
                h('div', { class: 'row' }, this.button, h('span', { class: 'field__hint' }, h('span', { class: 'kbd' }, 'Ctrl'), ' + ', h('span', { class: 'kbd' }, 'Enter')))),
            this.resultRoot,
        );
    }

    show() {}

    async submit() {
        const text1 = this.first.textarea.value.trim();
        const text2 = this.second.textarea.value.trim();
        const min = this.vocab.limits.min_text_chars;
        if (text1.length < min || text2.length < min) {
            this.error.hidden = false;
            replace(this.error, icon('alert'), `Her iki metin de en az ${min} karakter olmalıdır.`);
            (text1.length < min ? this.first : this.second).textarea.focus();
            return;
        }
        this.error.hidden = true;
        this.button.disabled = true;
        replace(this.button, icon('loader', 'spin'), 'Karşılaştırılıyor…');
        replace(this.resultRoot, h('section', { class: 'card' }, emptyState({ iconName: 'loader', title: 'Evraklar karşılaştırılıyor…', compact: true })));
        try {
            this.renderResult(await this.api.compare(text1, text2));
        } catch (error) {
            const retryBtn = h('button', { type: 'button', class: 'btn btn--primary btn--sm', onClick: () => this.submit() }, icon('refresh'), 'Tekrar dene');
            replace(this.resultRoot, h('div', { class: 'card card__body stack' },
                h('div', { class: 'alert alert--danger', role: 'alert' }, icon('circleX'), h('div', null, h('strong', null, 'Karşılaştırma yapılamadı'), error.message)),
                error.code === 'network' ? h('p', { class: 'muted' }, 'Sunucu bağlantısı kesildi. Sunucunun çalıştığından emin olun.') : null,
                h('div', { class: 'row' }, retryBtn)));
        } finally {
            this.button.disabled = false;
            replace(this.button, icon('compare'), 'Karşılaştır');
        }
    }

    renderResult(result) {
        const list = (items, empty) => items?.length
            ? h('ul', { class: 'list' }, items.map((item) => h('li', { class: 'row', style: { alignItems: 'flex-start', flexWrap: 'nowrap' } }, h('span', { style: { color: 'var(--primary)', marginTop: '3px' } }, icon('arrowRight')), item)))
            : h('p', { class: 'muted' }, empty);

        replace(this.resultRoot, h('section', { class: 'card card__body stack' },
            h('div', { class: 'row', style: { gap: '16px', flexWrap: 'nowrap' } },
                scoreRing(result.similarity_score, 'Benzerlik'),
                h('div', null, h('div', { class: 'panel__label' }, 'Benzerlik ve öneri'), h('p', null, result.recommendation || '—'))),
            h('div', { class: 'grid-2' },
                h('div', { class: 'panel' }, h('div', { class: 'panel__label' }, 'Ortak temalar'),
                    result.common_themes?.length ? h('div', { class: 'chips' }, result.common_themes.map((t) => h('span', { class: 'chip' }, t))) : h('p', { class: 'muted' }, 'Ortak tema bulunamadı.')),
                h('div', { class: 'panel' }, h('div', { class: 'panel__label' }, 'Farklar'), list(result.differences, 'Belirgin bir fark bulunamadı.'))),
            h('div', { class: 'grid-2' },
                h('div', { class: 'panel' }, h('div', { class: 'panel__label' }, 'Yalnızca birinci evrakta'), h('p', null, result.text1_unique || '—')),
                h('div', { class: 'panel' }, h('div', { class: 'panel__label' }, 'Yalnızca ikinci evrakta'), h('p', null, result.text2_unique || '—'))),
            h('div', { class: 'row', style: { justifyContent: 'flex-end' } },
                h('button', { type: 'button', class: 'btn btn--ghost btn--sm', onClick: () => {
                    const text = `Benzerlik: %${Math.round(result.similarity_score * 100)}\nOrtak temalar: ${(result.common_themes || []).join(', ') || '—'}\nÖneri: ${result.recommendation || '—'}`;
                    navigator.clipboard.writeText(text).then(() => this.toaster.success('Sonuç kopyalandı.'), () => this.toaster.error('Kopyalama başarısız.'));
                }}, icon('copy'), 'Sonucu kopyala'),
            ),
        ));
    }

    swap() {
        const tmp = this.first.textarea.value;
        this.first.textarea.value = this.second.textarea.value;
        this.second.textarea.value = tmp;
        this.first.textarea.dispatchEvent(new Event('input'));
        this.second.textarea.dispatchEvent(new Event('input'));
    }
}
