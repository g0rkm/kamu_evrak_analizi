import { h, icon, replace } from '../core/dom.js';
import { fmt } from '../core/vocabulary.js';

export class CompareView {
    title = 'Karşılaştır';

    constructor({ api, vocab, toaster }) {
        this.api = api;
        this.vocab = vocab;
        this.toaster = toaster;
        this.element = this.build();
    }

    textField(id, label, placeholder) {
        const counter = h('div', { style: { fontSize: '12px', color: 'var(--color-neutral-700)', marginTop: '4px' } });
        const textarea = h('textarea', {
            class: 'input', id, placeholder, style: { minHeight: '240px', fontSize: '15px' },
            onInput: () => {
                const len = textarea.value.trim().length;
                const max = this.vocab.limits.max_text_chars;
                counter.textContent = `${fmt.number(len)} / ${fmt.number(max)} karakter`;
                counter.style.color = len > max ? 'var(--danger)' : 'var(--color-neutral-700)';
            },
            onKeydown: (e) => { if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); this.submit(); } },
        });
        counter.textContent = `0 / ${fmt.number(this.vocab.limits.max_text_chars)} karakter`;
        return {
            textarea,
            element: h('div', { class: 'field' },
                h('label', { for: id, style: { fontSize: '14px', color: 'var(--color-text)' } }, label),
                textarea, counter),
        };
    }

    build() {
        this.first = this.textField('compareFirst', 'Birinci evrak', 'Birinci evrakın metnini yapıştırın…');
        this.second = this.textField('compareSecond', 'İkinci evrak', 'İkinci evrakın metnini yapıştırın…');
        this.error = h('p', { class: 'field__error', role: 'alert', hidden: true, style: { justifyContent: 'center' } });
        this.button = h('button', { type: 'button', class: 'btn btn-primary', style: { fontSize: '17px', padding: '12px 32px' }, onClick: () => this.submit() }, 'Karşılaştır');
        this.resultRoot = h('div', { 'aria-live': 'polite' });

        return h('section', { style: { display: 'flex', flexDirection: 'column', gap: '28px' } },
            h('div', { style: { textAlign: 'center' } },
                h('h1', { style: { margin: 0, fontWeight: 400 } }, 'Evrak karşılaştırma'),
                h('p', { style: { margin: '6px auto 0', color: 'var(--color-neutral-700)', maxWidth: '560px' } },
                    'İki evrakın metnini yan yana koyun; sistem benzerlikleri ve farkları sizin için listelesin.')),
            h('div', { style: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '20px' } },
                this.first.element, this.second.element),
            this.error,
            h('div', { style: { display: 'flex', justifyContent: 'center', gap: '12px', flexWrap: 'wrap' } },
                h('button', { type: 'button', class: 'btn btn-secondary', onClick: () => this.swap() }, 'Yerlerini değiştir'),
                this.button),
            this.resultRoot);
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
        const max = this.vocab.limits.max_text_chars;
        if (text1.length > max || text2.length > max) {
            this.error.hidden = false;
            replace(this.error, icon('alert'), `Her iki metin de en fazla ${fmt.number(max)} karakter olabilir.`);
            (text1.length > max ? this.first : this.second).textarea.focus();
            return;
        }
        this.error.hidden = true;
        this.button.disabled = true;
        replace(this.button, 'Karşılaştırılıyor…');
        replace(this.resultRoot, h('div', { class: 'card', style: { padding: '26px', textAlign: 'center', color: 'var(--color-neutral-700)' } }, 'Evraklar karşılaştırılıyor…'));
        try {
            this.renderResult(await this.api.compare(text1, text2));
        } catch (error) {
            replace(this.resultRoot, h('div', { class: 'card', style: { padding: '22px', gap: '12px' } },
                h('div', { class: 'alert alert--danger', role: 'alert' }, icon('circleX'), h('div', null, h('strong', null, 'Karşılaştırma yapılamadı'), error.message)),
                h('div', null, h('button', { type: 'button', class: 'btn btn-primary', onClick: () => this.submit() }, 'Tekrar dene'))));
        } finally {
            this.button.disabled = false;
            replace(this.button, 'Karşılaştır');
        }
    }

    renderResult(result) {
        const pct = Math.round((result.similarity_score || 0) * 100);
        const list = (items, empty) => items?.length
            ? h('ul', { style: { margin: 0, paddingLeft: '18px', fontSize: '14px', display: 'flex', flexDirection: 'column', gap: '6px' } },
                items.map((item) => h('li', null, item)))
            : h('p', { style: { margin: 0, fontSize: '14px', color: 'var(--color-neutral-700)' } }, empty);

        replace(this.resultRoot, h('div', { class: 'card split', style: { padding: '26px', display: 'grid', gridTemplateColumns: '200px repeat(2, minmax(0, 1fr))', gap: '28px' } },
            h('div', { style: { textAlign: 'center', borderRight: '1px solid var(--color-divider)', paddingRight: '20px' } },
                h('div', { class: 'card-kicker' }, 'Benzerlik'),
                h('div', { style: { fontFamily: 'var(--font-heading)', fontSize: '56px', lineHeight: 1.1, fontVariantNumeric: 'tabular-nums' } }, `%${pct}`),
                h('div', { style: { fontSize: '13px', color: 'var(--color-neutral-700)' } }, result.recommendation || '—')),
            h('div', null,
                h('div', { class: 'card-kicker', style: { marginBottom: '8px' } }, 'Ortak noktalar'),
                list(result.common_themes, 'Ortak nokta bulunamadı.'),
                result.text1_unique ? h('p', { style: { margin: '12px 0 0', fontSize: '13px', color: 'var(--color-neutral-700)' } }, `Yalnızca birinci evrakta: ${result.text1_unique}`) : null),
            h('div', null,
                h('div', { class: 'card-kicker', style: { marginBottom: '8px' } }, 'Farklar'),
                list(result.differences, 'Belirgin bir fark bulunamadı.'),
                result.text2_unique ? h('p', { style: { margin: '12px 0 0', fontSize: '13px', color: 'var(--color-neutral-700)' } }, `Yalnızca ikinci evrakta: ${result.text2_unique}`) : null)));
    }

    swap() {
        const tmp = this.first.textarea.value;
        this.first.textarea.value = this.second.textarea.value;
        this.second.textarea.value = tmp;
        this.first.textarea.dispatchEvent(new Event('input'));
        this.second.textarea.dispatchEvent(new Event('input'));
    }
}
