import { ApiClient } from '../core/api.js';
import { h, replace, storage } from '../core/dom.js';
import { Vocabulary } from '../core/vocabulary.js';

const PRIORITY_LABELS = { acil: 'Acil', urgent: 'Acil', yuksek: 'Yüksek', high: 'Yüksek', normal: 'Normal', dusuk: 'Düşük', low: 'Düşük' };

const SAMPLES_BY_TYPE = {
    dilekce: `T.C.\nÖRNEK BELEDİYE BAŞKANLIĞINA\n\nKonu: Bilgi edinme başvurusu\n\n4982 sayılı Bilgi Edinme Hakkı Kanunu kapsamında mahallemizde yürütülen imar planı çalışmalarına ilişkin kararların tarafıma iletilmesini arz ederim.\n\nAd Soyad: Mehmet Demir\nTarih: 28.10.2026`,
    rapor: `T.C.\nÖRNEK KURUM BAŞKANLIĞI\nTeknik İnceleme Raporu\n\nKonu: Hizmet binası enerji verimliliği incelemesi\n\n1. Amaç ve kapsam: Hizmet binasının ısıtma ve aydınlatma tüketiminin değerlendirilmesi.\n2. Bulgular: Yıllık tüketimde %18 tasarruf potansiyeli tespit edilmiştir.\n3. Sonuç ve öneri: Bakım ve yalıtım programının uygulanması arz olunur.`,
    sozlesme: `HİZMET ALIM SÖZLEŞMESİ\n\nTaraflar: Bir tarafta Örnek İdare, diğer tarafta Yüklenici.\nKonu: 4734 sayılı Kamu İhale Kanunu kapsamında bakım ve destek hizmeti alımı.\nSüre: İşe başlama tarihinden itibaren 12 (on iki) aydır.`,
    tutanak: `TOPLANTI TUTANAĞI\n\nTarih: 28.10.2026\nKonu: Haftalık evrak değerlendirme toplantısı\n\nGündem maddeleri görüşülmüş, bekleyen başvuruların ilgili müdürlüklere ivedilikle yönlendirilmesine karar verilmiştir.`,
};

export class TemplatesView {
    title = 'Evrak şablonları';

    constructor(container) {
        this._container = container;
        this._api = new ApiClient();
        this._vocab = new Vocabulary();
    }

    async render(root = this._container) {
        this.formBox = this._buildForm();
        this.listRoot = h('div', { id: 'templatesList' }, h('div', { class: 'loading-line' }, 'Yükleniyor…'));

        const section = h('section', { style: { display: 'flex', flexDirection: 'column', gap: '26px' } },
            h('div', { class: 'page-bar' },
                h('div', null,
                    h('h1', { style: { margin: 0, fontWeight: 400 } }, 'Evrak şablonları'),
                    h('p', { style: { margin: '4px 0 0', color: 'var(--color-neutral-700)' } }, 'Sık kullanılan yazı türleri için hazır kalıplar. Birini seçip doldurmaya başlayın.')),
                h('button', {
                    type: 'button', class: 'btn btn-primary', id: 'addTemplateBtn',
                    onClick: () => { this.formBox.hidden = !this.formBox.hidden; },
                }, 'Yeni şablon oluştur')),
            this.formBox,
            this.listRoot);

        replace(root, section);
        await this._loadTemplates();
    }

    _buildForm() {
        this.tplName = h('input', { class: 'input', id: 'tplName', placeholder: 'Örn. Bilgi edinme dilekçesi' });
        this.tplDocType = h('input', { class: 'input', id: 'tplDocType', placeholder: 'Örn. dilekce, rapor, tutanak' });
        this.tplDesc = h('input', { class: 'input', id: 'tplDesc', placeholder: 'Kısa açıklama' });
        this.tplTags = h('input', { class: 'input', id: 'tplTags', placeholder: 'Etiketler (virgülle)' });
        this.tplPriority = h('select', { class: 'input', id: 'tplPriority' },
            h('option', { value: 'normal' }, 'Normal'),
            h('option', { value: 'high' }, 'Yüksek'),
            h('option', { value: 'urgent' }, 'Acil'),
            h('option', { value: 'low' }, 'Düşük'));

        const box = h('div', { class: 'card', id: 'templateForm', hidden: true, style: { padding: '22px', gap: '14px' } },
            h('div', { class: 'card-title' }, 'Yeni şablon'),
            h('div', { style: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px' } },
                h('div', { class: 'field' }, h('label', { for: 'tplName' }, 'Şablon adı'), this.tplName),
                h('div', { class: 'field' }, h('label', { for: 'tplDocType' }, 'Evrak türü'), this.tplDocType),
                h('div', { class: 'field' }, h('label', { for: 'tplPriority' }, 'Varsayılan öncelik'), this.tplPriority),
                h('div', { class: 'field' }, h('label', { for: 'tplTags' }, 'Etiketler'), this.tplTags)),
            h('div', { class: 'field' }, h('label', { for: 'tplDesc' }, 'Açıklama'), this.tplDesc),
            h('div', { style: { display: 'flex', gap: '8px', justifyContent: 'flex-end' } },
                h('button', { type: 'button', class: 'btn btn-secondary', id: 'cancelTemplateBtn', onClick: () => { box.hidden = true; } }, 'Vazgeç'),
                h('button', { type: 'button', class: 'btn btn-primary', id: 'saveTemplateBtn', onClick: () => this._saveTemplate() }, 'Kaydet')));
        return box;
    }

    async _loadTemplates() {
        try {
            const resp = await this._api.request('/templates');
            this._renderList(resp.templates || []);
        } catch {
            replace(this.listRoot, h('p', { class: 'error-text' }, 'Şablonlar yüklenemedi.'));
        }
    }

    _renderList(templates) {
        if (!templates.length) {
            replace(this.listRoot, h('p', { class: 'muted' }, 'Henüz şablon yok.'));
            return;
        }
        replace(this.listRoot, h('div', { style: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '18px' } },
            ...templates.map((t) => {
                const prio = PRIORITY_LABELS[t.default_priority] || t.default_priority || 'Normal';
                return h('div', { class: 'card', style: { padding: '22px', gap: '10px' } },
                    h('div', { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center' } },
                        h('span', { class: 'card-kicker' }, t.builtin ? 'Hazır şablon' : 'Özel şablon'),
                        h('span', { class: 'tag tag-neutral' }, `Öncelik: ${prio}`)),
                    h('div', { style: { fontFamily: 'var(--font-heading)', fontSize: '24px' } }, t.name),
                    h('p', { class: 'card-body', style: { fontSize: '14px' } }, t.description || this._vocab.documentType(t.document_type)),
                    h('div', { style: { display: 'flex', gap: '8px', borderTop: '1px solid var(--color-divider)', paddingTop: '12px' } },
                        h('button', { type: 'button', class: 'btn btn-primary', style: { flex: 1 }, onClick: () => this._useTemplate(t) }, 'Kullan'),
                        h('button', { type: 'button', class: 'btn btn-secondary', onClick: () => this._previewTemplate(t) }, 'Önizle'),
                        !t.builtin ? h('button', { type: 'button', class: 'btn btn-ghost btn--muted', onClick: () => this._deleteTemplate(t.id) }, 'Sil') : null));
            })));
    }

    _sampleFor(t) {
        const key = String(t.document_type || t.id || '').toLowerCase();
        return SAMPLES_BY_TYPE[key] || `${t.name}\n\nKonu: ${t.description || t.name}\n\n[Evrak metnini buraya yazın]`;
    }

    _useTemplate(t) {
        try {
            sessionStorage.setItem('draftTitle', t.name);
            sessionStorage.setItem('draftText', this._sampleFor(t));
        } catch {}
        storage.set('inputMode', 'text');
        location.hash = '#/analiz';
    }

    _previewTemplate(t) {
        const dialog = h('dialog', { class: 'dialog' },
            h('div', { class: 'dialog-title' }, t.name),
            h('div', { class: 'dialog-body', style: { whiteSpace: 'pre-wrap' } }, this._sampleFor(t)),
            h('div', { class: 'dialog-actions' },
                h('button', { type: 'button', class: 'btn btn-secondary', onClick: () => { dialog.close(); dialog.remove(); } }, 'Kapat'),
                h('button', { type: 'button', class: 'btn btn-primary', onClick: () => { dialog.close(); dialog.remove(); this._useTemplate(t); } }, 'Bu şablonu kullan')));
        document.body.append(dialog);
        dialog.showModal();
    }

    async _saveTemplate() {
        const name = this.tplName.value.trim();
        const docType = this.tplDocType.value.trim();
        if (!name || !docType) return;
        try {
            await this._api.request('/templates', {
                method: 'POST',
                json: {
                    name,
                    document_type: docType,
                    description: this.tplDesc.value.trim(),
                    default_tags: this.tplTags.value.split(',').map((t) => t.trim()).filter(Boolean),
                    default_priority: this.tplPriority.value,
                },
            });
            this.formBox.hidden = true;
            this.tplName.value = '';
            this.tplDocType.value = '';
            this.tplDesc.value = '';
            this.tplTags.value = '';
            await this._loadTemplates();
        } catch {}
    }

    async _deleteTemplate(id) {
        try {
            await this._api.request(`/templates/${encodeURIComponent(id)}`, { method: 'DELETE' });
            await this._loadTemplates();
        } catch {}
    }
}
