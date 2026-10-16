import { badge, downloadBlob, emptyState, h, icon, meter, replace, scoreRing } from '../core/dom.js';
import { Tabs } from '../core/ui.js';
import { DRAFT_STATUS, ROUTING_STATUS, SEVERITY, fmt } from '../core/vocabulary.js';

/** Memur onay kararlarını (taslak / yönlendirme) sunucuya kaydeder. */
class ReviewController {
    constructor({ api, toaster, historyId, review }) {
        this.api = api;
        this.toaster = toaster;
        this.historyId = historyId;
        this.state = { draft_status: 'pending', routing_status: 'pending', ...(review || {}) };
        this.listeners = new Set();
    }

    subscribe(listener) {
        this.listeners.add(listener);
        return () => this.listeners.delete(listener);
    }

    async update(patch, successMessage) {
        if (!this.historyId) {
            this.state = { ...this.state, ...patch };
            this.listeners.forEach((fn) => fn(this.state));
            return true;
        }
        try {
            this.state = await this.api.updateReview(this.historyId, patch);
            this.listeners.forEach((fn) => fn(this.state));
            if (successMessage) this.toaster.success(successMessage);
            return true;
        } catch (error) {
            this.toaster.error(`Karar kaydedilemedi: ${error.message}`);
            return false;
        }
    }
}

function confidenceText(score) {
    if (score >= 0.8) return 'Yüksek güven — sonuçlar kendi içinde tutarlı.';
    if (score >= 0.5) return 'Orta güven — düzeltmeleri ve uyarıları gözden geçirin.';
    return 'Düşük güven — sonuçları göndermeden önce elle kontrol edin.';
}

function confidenceVariant(score) {
    return score >= 0.8 ? 'success' : score >= 0.5 ? 'warning' : 'danger';
}

function panel(label, ...children) {
    return h('div', { class: 'panel' }, h('div', { class: 'panel__label' }, label), ...children);
}

function sectionTitle(iconName, text, extra = null) {
    return h('h3', { class: 'section-title' }, icon(iconName), text, extra);
}

export class ResultView {
    constructor({ api, vocab, toaster, onNewAnalysis }) {
        this.api = api;
        this.vocab = vocab;
        this.toaster = toaster;
        this.onNewAnalysis = onNewAnalysis;
        this.activeTab = 'overview';
    }

    render(result, { historyId = null, review = null } = {}) {
        if (historyId !== this.historyId) this.activeTab = 'overview';
        this.result = result;
        this.historyId = historyId;
        this.review = new ReviewController({ api: this.api, toaster: this.toaster, historyId, review });

        const validation = result.validation || [];
        this.piiEntries = validation.filter((v) => v.field?.startsWith('pii.'));
        this.leakEntries = validation.filter((v) => v.field?.startsWith('draft_pii_leak.'));
        const attention = validation.filter((v) => v.severity !== 'info').length;
        const analysis = result.analysis || {};

        // Sekme her açıldığında yeniden çizilir; önceki sekmenin abonelikleri bırakılır.
        this.tabSubscriptions = [];
        const scoped = (render) => () => {
            this.tabSubscriptions.forEach((unsubscribe) => unsubscribe());
            this.tabSubscriptions = [];
            return render();
        };

        const tabs = new Tabs([
            { id: 'overview', label: 'Genel Bakış', icon: 'file', render: scoped(() => this.renderOverview()) },
            { id: 'content', label: 'İçerik', icon: 'network', count: (analysis.missing_fields || []).length || null, countVariant: 'warning', render: scoped(() => this.renderContent()) },
            { id: 'legislation', label: 'Mevzuat', icon: 'scale', count: (analysis.legislation_matches || []).length || null, render: scoped(() => this.renderLegislation()) },
            { id: 'draft', label: 'Yazı Taslağı', icon: 'pen', render: scoped(() => this.renderDraft()) },
            { id: 'routing', label: 'Yönlendirme', icon: 'route', render: scoped(() => this.renderRouting()) },
            { id: 'validation', label: 'Doğrulama', icon: 'shieldCheck', count: attention || null, countVariant: 'warning', render: scoped(() => this.renderValidation()) },
            { id: 'trace', label: 'İşlem Kaydı', icon: 'terminal', render: scoped(() => this.renderTrace()) },
        ], { initial: this.activeTab, onChange: (id) => { this.activeTab = id; } });

        return h('div', { class: 'stack' },
            this.renderHero(),
            result.status === 'partial' ? this.renderPartialWarning() : null,
            h('section', { class: 'card', 'aria-label': 'Analiz ayrıntıları' }, tabs.element),
        );
    }

    // ── Başlık ───────────────────────────────────────────

    renderHero() {
        const { result, vocab } = this;
        const classification = result.analysis?.classification || {};
        const routing = result.routing;
        const score = result.confidence_score || 0;
        const unitValue = h('div', { class: 'kpi__value' }, this.currentUnit() || '—');
        this.review.subscribe(() => { unitValue.textContent = this.currentUnit() || '—'; });

        const exportButton = h('button', { type: 'button', class: 'btn btn--secondary btn--sm', onClick: () => this.exportJson() }, icon('download'), 'JSON indir');
        const newButton = h('button', { type: 'button', class: 'btn btn--primary btn--sm', onClick: () => this.onNewAnalysis?.() }, icon('plus'), 'Yeni analiz');

        return h('section', { class: 'card card__body', 'aria-label': 'Analiz özeti' },
            h('div', { class: 'result-hero' },
                h('div', null,
                    h('h2', { class: 'result-hero__title' }, result.source_name || 'Analiz sonucu'),
                    h('div', { class: 'result-hero__meta' },
                        h('span', null, icon('clock'), fmt.date(result.created_at)),
                        h('span', null, icon(result.input_kind === 'file' ? 'file' : 'type'), result.input_kind === 'file' ? 'Dosya' : 'Metin girişi'),
                        h('span', null, icon('refresh'), `${fmt.seconds(result.processing_time)} sürdü`),
                    ),
                ),
                h('div', { class: 'result-hero__actions' }, exportButton, newButton),
            ),
            h('div', { class: 'kpis' },
                h('div', { class: 'kpi' }, h('div', { class: 'kpi__label' }, 'Evrak türü'),
                    h('div', { class: 'kpi__value' }, badge(vocab.documentType(classification.document_type), 'primary', 'badge--lg'))),
                h('div', { class: 'kpi' }, h('div', { class: 'kpi__label' }, 'Genel güven'),
                    h('div', { class: 'kpi__value kpi__value--lg' }, fmt.percent(score)),
                    meter(score, confidenceVariant(score))),
                h('div', { class: 'kpi' }, h('div', { class: 'kpi__label' }, 'Öncelik'),
                    h('div', { class: 'kpi__value' }, routing ? badge(vocab.priority(routing.priority), vocab.priorityVariant(routing.priority), 'badge--lg') : '—')),
                h('div', { class: 'kpi', title: this.currentUnit() || '' }, h('div', { class: 'kpi__label' }, 'Hedef birim'), unitValue),
            ),
        );
    }

    renderPartialWarning() {
        return h('div', { class: 'alert alert--warning', role: 'status' }, icon('alert'),
            h('div', null,
                h('strong', null, 'Analiz kısmen tamamlandı'),
                'Bazı adımlar başarısız oldu; bu bölümlerde varsayılan değerler gösteriliyor.',
                h('ul', null, (this.result.warnings || []).map((w) => h('li', null, w))),
            ));
    }

    // ── Sekmeler ─────────────────────────────────────────

    renderOverview() {
        const analysis = this.result.analysis || {};
        const cls = analysis.classification || {};
        const keywords = analysis.keywords || [];

        return h('div', { class: 'stack' },
            panel('Yönetici özeti', h('p', null, analysis.summary || 'Özet oluşturulamadı.')),
            h('div', { class: 'grid-2' },
                panel('Sınıflandırma',
                    h('div', { class: 'row' }, badge(this.vocab.documentType(cls.document_type), 'primary'),
                        cls.sub_type ? h('span', { class: 'muted small' }, cls.sub_type) : null),
                    h('div', { class: 'row', style: { marginTop: '10px' } },
                        h('div', { class: 'grow' }, meter(cls.confidence, confidenceVariant(cls.confidence || 0))),
                        h('strong', { class: 'small' }, fmt.percent(cls.confidence))),
                    h('p', { class: 'small muted', style: { marginTop: '8px' } }, cls.reasoning || 'Gerekçe belirtilmedi.')),
                panel('Anahtar kelimeler',
                    keywords.length ? h('div', { class: 'chips' }, keywords.map((k) => h('span', { class: 'chip' }, icon('tag'), k)))
                        : h('p', { class: 'muted' }, 'Anahtar kelime bulunamadı.')),
            ),
            h('div', null, sectionTitle('alert', 'Dikkat gerektirenler'), this.renderAttentionList()),
        );
    }

    renderAttentionList() {
        const analysis = this.result.analysis || {};
        const corrections = (this.result.validation || []).filter((v) => v.severity === 'correction');
        const critical = (analysis.missing_fields || []).filter((m) => m.is_critical);
        const items = [];

        if (this.leakEntries.length) {
            items.push(['danger', 'shield', 'Taslak yazıda kişisel veri var', 'Göndermeden önce taslaktaki kişisel verileri çıkarın.']);
        }
        if (critical.length) {
            items.push(['warning', 'alert', `${critical.length} kritik eksik alan`, critical.map((m) => fieldLabel(m.field_name)).join(', ')]);
        }
        if (this.piiEntries.length) {
            items.push(['pii', 'shield', `${this.piiEntries.length} kişisel veri tespit edildi`, 'KVKK kapsamında paylaşım öncesi maskeleme gerekebilir.']);
        }
        if (corrections.length) {
            items.push(['info', 'wrench', `Muhakeme ajanı ${corrections.length} düzeltme yaptı`, corrections.map((c) => this.vocab.validationField(c.field)).join(', ')]);
        }
        if (!items.length) {
            return h('div', { class: 'alert alert--success' }, icon('circleCheck'), h('div', null, h('strong', null, 'Kritik bir sorun tespit edilmedi'), 'Yine de taslak ve yönlendirmeyi onaylamadan önce gözden geçirin.'));
        }
        return h('div', { class: 'stack-sm' }, items.map(([variant, iconName, title, text]) =>
            h('div', { class: `alert alert--${variant}` }, icon(iconName), h('div', null, h('strong', null, title), text))));
    }

    renderContent() {
        const analysis = this.result.analysis || {};
        const entities = analysis.entities || [];
        const missing = analysis.missing_fields || [];

        const entityTable = entities.length
            ? h('div', { class: 'table-wrap' }, h('table', { class: 'table' },
                h('thead', null, h('tr', null, h('th', { scope: 'col' }, 'Tür'), h('th', { scope: 'col' }, 'Değer'), h('th', { scope: 'col' }, 'Konum'))),
                h('tbody', null, entities.map((e) => h('tr', null,
                    h('td', null, badge(this.vocab.entity(e.entity_type))),
                    h('td', null, e.value || '—'),
                    h('td', { class: 'muted small' }, e.position || '—'))))))
            : emptyState({ iconName: 'network', title: 'Varlık bulunamadı', compact: true });

        const missingList = missing.length
            ? h('ul', { class: 'list' }, missing.map((m) => h('li', { class: 'list-item' },
                h('span', { class: 'list-item__icon', style: { color: m.is_critical ? 'var(--danger)' : 'var(--warning)' } }, icon('alert')),
                h('div', { class: 'grow' },
                    h('div', { class: 'row' }, h('span', { class: 'list-item__title' }, fieldLabel(m.field_name)),
                        m.is_critical ? badge('Kritik', 'danger') : badge('Önerilen', 'warning')),
                    m.description ? h('p', { class: 'small muted' }, m.description) : null))))
            : h('div', { class: 'alert alert--success' }, icon('circleCheck'), 'Eksik alan tespit edilmedi.');

        return h('div', { class: 'stack' },
            h('div', null, sectionTitle('network', 'Çıkarılan bilgiler'), entityTable),
            h('div', null, sectionTitle('alert', 'Eksik alanlar'), missingList),
        );
    }

    renderLegislation() {
        const matches = this.result.analysis?.legislation_matches || [];
        if (!matches.length) {
            return emptyState({ iconName: 'scale', title: 'Eşleşen mevzuat bulunamadı', text: 'Evrak metniyle ilişkilendirilebilecek bir mevzuat tespit edilmedi.' });
        }
        return h('div', { class: 'stack-sm' }, matches.map((m) => h('article', { class: 'legislation-card' },
            h('div', { class: 'row row--between' },
                h('h4', null, m.legislation_name, m.article ? h('span', { class: 'muted small' }, ` · Madde ${String(m.article).replace(/^madde\s*/i, '')}`) : null),
                badge(`İlgi ${fmt.percent(m.relevance_score)}`, 'primary')),
            meter(m.relevance_score),
            m.summary ? h('p', { class: 'small', style: { color: 'var(--text-2)' } }, m.summary) : null)));
    }

    // ── Taslak ───────────────────────────────────────────

    draftBody() {
        return this.review.state.draft_body ?? this.result.draft?.body ?? '';
    }

    draftPlainText() {
        const d = this.result.draft || {};
        return [d.formal_greeting, d.subject ? `Konu: ${d.subject}` : '', this.draftBody(), d.closing, d.attachments_note ? `Ek: ${d.attachments_note}` : '']
            .filter(Boolean).join('\n\n');
    }

    renderDraft() {
        const draft = this.result.draft;
        if (!draft) {
            return emptyState({ iconName: 'pen', title: 'Taslak oluşturulamadı', text: 'Bu evrak için yazı taslağı üretilemedi. İşlem Kaydı sekmesinden ayrıntılara bakabilirsiniz.' });
        }

        const body = h('div', { class: 'letter__body' }, this.draftBody());
        const letter = h('article', { class: 'letter', 'aria-label': 'Resmî yazı taslağı' },
            draft.formal_greeting ? h('div', null, draft.formal_greeting) : null,
            draft.subject ? h('div', { class: 'letter__subject' }, h('strong', null, 'Konu: '), draft.subject) : null,
            body,
            draft.closing ? h('div', { class: 'letter__closing' }, draft.closing) : null,
            draft.attachments_note ? h('div', { class: 'letter__attachments' }, h('strong', null, 'Ek: '), draft.attachments_note) : null,
        );

        const editor = h('div', { class: 'stack-sm', hidden: true });
        const reviewBar = h('div', { class: 'review-bar' });
        const renderBar = () => replace(reviewBar, ...this.draftReviewControls(letter, editor));
        renderBar();
        this.tabSubscriptions.push(this.review.subscribe(() => { body.textContent = this.draftBody(); renderBar(); }));

        return h('div', { class: 'stack' },
            reviewBar,
            this.leakEntries.length ? h('div', { class: 'alert alert--danger' }, icon('shield'),
                h('div', null, h('strong', null, 'Taslakta kişisel veri tespit edildi'),
                    this.leakEntries.map((e) => `${this.vocab.piiLabel(e.field.split('.')[1])} (${e.original_value})`).join(', '))) : null,
            h('div', { class: 'row small muted' }, icon('tag'), 'Yazı türü:', badge(this.vocab.draftType(draft.draft_type), 'primary')),
            editor,
            letter,
            draft.tone_check ? h('div', { class: 'alert alert--info' }, icon('info'), h('div', null, h('strong', null, 'Üslup değerlendirmesi'), draft.tone_check)) : null,
        );
    }

    draftReviewControls(letter, editor) {
        const status = this.review.state.draft_status || 'pending';
        const info = DRAFT_STATUS[status] || DRAFT_STATUS.pending;
        const controls = [
            h('span', { class: 'row grow' }, icon('userCheck'), h('strong', null, 'Memur kararı'), badge(info.label, info.variant)),
        ];

        if (status === 'pending') {
            controls.push(
                h('button', { type: 'button', class: 'btn btn--success btn--sm', onClick: () => this.review.update({ draft_status: 'approved' }, 'Taslak onaylandı.') }, icon('check'), 'Onayla'),
                h('button', { type: 'button', class: 'btn btn--secondary btn--sm', onClick: () => this.openEditor(letter, editor) }, icon('pencil'), 'Düzenle'),
                h('button', { type: 'button', class: 'btn btn--danger-ghost btn--sm', onClick: () => this.openRejectForm(editor) }, icon('x'), 'Reddet'),
            );
        } else {
            if (status === 'rejected' && this.review.state.reject_reason) {
                controls.push(h('span', { class: 'small muted' }, `Gerekçe: ${this.review.state.reject_reason}`));
            }
            controls.push(h('button', {
                type: 'button', class: 'btn btn--ghost btn--sm',
                onClick: () => this.review.update({ draft_status: 'pending', reject_reason: null }),
            }, icon('refresh'), 'Kararı geri al'));
        }

        controls.push(
            h('button', { type: 'button', class: 'btn btn--ghost btn--icon btn--sm', title: 'Kopyala', 'aria-label': 'Taslağı kopyala', onClick: () => this.copyDraft() }, icon('copy')),
            h('button', { type: 'button', class: 'btn btn--ghost btn--icon btn--sm', title: 'Metin olarak indir', 'aria-label': 'Taslağı metin olarak indir', onClick: () => downloadBlob(this.draftPlainText(), `taslak_${this.historyId || 'yazi'}.txt`, 'text/plain;charset=utf-8') }, icon('download')),
            h('button', { type: 'button', class: 'btn btn--ghost btn--icon btn--sm', title: 'Yazdır', 'aria-label': 'Taslağı yazdır', onClick: () => window.print() }, icon('printer')),
        );
        return controls;
    }

    openEditor(letter, editor) {
        const textarea = h('textarea', { class: 'textarea', id: 'draftEditor', value: this.draftBody(), style: { minHeight: '320px', fontFamily: 'var(--font-serif)', fontSize: '15px' } });
        const close = () => { editor.hidden = true; letter.hidden = false; editor.replaceChildren(); };
        replace(editor,
            h('label', { class: 'field__label', for: 'draftEditor' }, 'Taslak metnini düzenleyin'),
            textarea,
            h('div', { class: 'row' },
                h('button', {
                    type: 'button', class: 'btn btn--primary btn--sm',
                    onClick: async () => { if (await this.review.update({ draft_status: 'edited', draft_body: textarea.value }, 'Düzenlenen taslak kaydedildi.')) close(); },
                }, icon('check'), 'Kaydet ve onayla'),
                h('button', { type: 'button', class: 'btn btn--ghost btn--sm', onClick: close }, 'Vazgeç')),
        );
        letter.hidden = true;
        editor.hidden = false;
        textarea.focus();
    }

    openRejectForm(editor) {
        const input = h('input', { class: 'input', id: 'rejectReason', placeholder: 'Örn. Muhatap kurum hatalı, ilgi tarihi eksik', maxlength: 1000 });
        const close = () => { editor.hidden = true; editor.replaceChildren(); };
        replace(editor,
            h('label', { class: 'field__label', for: 'rejectReason' }, 'Reddetme gerekçesi'),
            input,
            h('div', { class: 'row' },
                h('button', {
                    type: 'button', class: 'btn btn--danger btn--sm',
                    onClick: async () => {
                        if (!input.value.trim()) { input.setAttribute('aria-invalid', 'true'); input.focus(); return; }
                        if (await this.review.update({ draft_status: 'rejected', reject_reason: input.value.trim() }, 'Taslak reddedildi.')) close();
                    },
                }, 'Reddi kaydet'),
                h('button', { type: 'button', class: 'btn btn--ghost btn--sm', onClick: close }, 'Vazgeç')),
        );
        editor.hidden = false;
        input.focus();
    }

    async copyDraft() {
        try {
            await navigator.clipboard.writeText(this.draftPlainText());
            this.toaster.success('Taslak panoya kopyalandı.');
        } catch {
            this.toaster.error('Panoya erişilemedi. Metni seçip elle kopyalayın.');
        }
    }

    // ── Yönlendirme ──────────────────────────────────────

    currentUnit() {
        return this.review.state.routing_unit || this.result.routing?.target_unit || '';
    }

    renderRouting() {
        const routing = this.result.routing;
        if (!routing) {
            return emptyState({ iconName: 'route', title: 'Yönlendirme yapılamadı', text: 'Bu evrak için birim önerisi üretilemedi.' });
        }
        const unitText = h('p', { style: { fontSize: '17px', fontWeight: 700, marginTop: '2px' } }, this.currentUnit());
        const reviewBar = h('div', { class: 'review-bar' });
        const changeArea = h('div', { class: 'stack-sm', hidden: true });
        const renderBar = () => replace(reviewBar, ...this.routingReviewControls(changeArea));
        renderBar();
        this.tabSubscriptions.push(this.review.subscribe(() => { unitText.textContent = this.currentUnit(); renderBar(); }));

        const alternatives = routing.alternative_units || [];
        const actions = routing.requires_action || [];
        return h('div', { class: 'stack' },
            reviewBar,
            changeArea,
            h('div', { class: 'grid-2' },
                panel('Hedef birim', h('div', { class: 'row' }, h('span', { style: { color: 'var(--primary)', fontSize: '20px' } }, icon('building')), unitText)),
                panel('Öncelik', badge(this.vocab.priority(routing.priority), this.vocab.priorityVariant(routing.priority), 'badge--lg'))),
            panel('Gerekçe', h('p', null, routing.reasoning || 'Gerekçe belirtilmedi.')),
            h('div', { class: 'grid-2' },
                panel('Alternatif birimler', alternatives.length ? h('div', { class: 'chips' }, alternatives.map((u) => h('span', { class: 'chip' }, u))) : h('p', { class: 'muted' }, 'Alternatif önerilmedi.')),
                panel('Birimden beklenen eylemler', actions.length
                    ? h('ul', { class: 'list' }, actions.map((a) => h('li', { class: 'row', style: { alignItems: 'flex-start' } }, h('span', { style: { color: 'var(--primary)', marginTop: '2px' } }, icon('arrowRight')), a)))
                    : h('p', { class: 'muted' }, 'Belirtilmiş bir eylem yok.'))),
        );
    }

    routingReviewControls(changeArea) {
        const status = this.review.state.routing_status || 'pending';
        const info = ROUTING_STATUS[status] || ROUTING_STATUS.pending;
        const controls = [h('span', { class: 'row grow' }, icon('userCheck'), h('strong', null, 'Yönlendirme kararı'), badge(info.label, info.variant))];
        if (status === 'pending') {
            controls.push(
                h('button', { type: 'button', class: 'btn btn--success btn--sm', onClick: () => this.review.update({ routing_status: 'approved' }, 'Yönlendirme onaylandı.') }, icon('check'), 'Onayla'),
                h('button', { type: 'button', class: 'btn btn--secondary btn--sm', onClick: () => this.openUnitChooser(changeArea) }, icon('compare'), 'Birimi değiştir'),
            );
        } else {
            controls.push(h('button', {
                type: 'button', class: 'btn btn--ghost btn--sm',
                onClick: () => this.review.update({ routing_status: 'pending', routing_unit: null }),
            }, icon('refresh'), 'Kararı geri al'));
        }
        return controls;
    }

    openUnitChooser(area) {
        const current = this.currentUnit();
        const select = h('select', { class: 'select', id: 'unitSelect' },
            h('option', { value: '' }, 'Birim seçin…'),
            this.vocab.units.map((u) => h('option', { value: u.label, selected: u.label === current }, u.label)));
        const close = () => { area.hidden = true; area.replaceChildren(); };
        replace(area,
            h('label', { class: 'field__label', for: 'unitSelect' }, 'Evrakın yönlendirileceği birim'),
            select,
            h('div', { class: 'row' },
                h('button', {
                    type: 'button', class: 'btn btn--primary btn--sm',
                    onClick: async () => {
                        if (!select.value) { select.focus(); return; }
                        if (await this.review.update({ routing_status: 'changed', routing_unit: select.value }, 'Yönlendirme güncellendi.')) close();
                    },
                }, 'Kaydet'),
                h('button', { type: 'button', class: 'btn btn--ghost btn--sm', onClick: close }, 'Vazgeç')),
        );
        area.hidden = false;
        select.focus();
    }

    // ── Doğrulama ────────────────────────────────────────

    renderValidation() {
        const validation = this.result.validation || [];
        const score = this.result.confidence_score || 0;
        const corrections = validation.filter((v) => v.severity === 'correction').length;
        const warnings = validation.filter((v) => v.severity === 'warning').length;

        const header = h('div', { class: 'panel row', style: { gap: '16px' } },
            scoreRing(score, 'Genel güven skoru'),
            h('div', { class: 'grow' },
                h('div', { class: 'panel__label' }, 'Genel güven skoru'),
                h('p', null, confidenceText(score)),
                h('p', { class: 'small muted' }, `${corrections} düzeltme · ${warnings} uyarı · kural tabanlı muhakeme ajanı tarafından hesaplandı`)));

        const pii = this.piiEntries.length ? this.renderPiiSummary() : null;
        const list = validation.length
            ? h('div', { class: 'stack-sm' }, validation.map((v) => this.renderFinding(v)))
            : h('div', { class: 'alert alert--success' }, icon('circleCheck'), 'Doğrulama kurallarının tamamı sorunsuz geçti.');

        return h('div', { class: 'stack' }, header, pii, h('div', null, sectionTitle('listChecks', 'Doğrulama bulguları'), list));
    }

    renderPiiSummary() {
        const counts = {};
        this.piiEntries.forEach((e) => {
            const type = e.field.split('.')[1];
            counts[type] = (counts[type] || 0) + 1;
        });
        return h('div', { class: 'alert alert--pii' }, icon('shield'),
            h('div', { class: 'grow' },
                h('strong', null, `Kişisel veri (KVKK) tespiti: ${this.piiEntries.length} kayıt`),
                h('div', { class: 'chips', style: { marginTop: '6px' } },
                    Object.entries(counts).map(([type, count]) => badge(`${this.vocab.piiLabel(type)}: ${count}`, 'pii')))));
    }

    renderFinding(entry) {
        const isPii = entry.field?.startsWith('pii.') || entry.field?.startsWith('draft_pii_leak.');
        const severity = SEVERITY[entry.severity] || SEVERITY.info;
        const variant = isPii && entry.severity !== 'warning' ? 'pii' : entry.severity || 'info';
        const original = this.vocab.validationValue(entry.field, entry.original_value);
        const corrected = this.vocab.validationValue(entry.field, entry.corrected_value);

        return h('div', { class: `finding finding--${variant}` },
            h('span', { class: 'finding__icon' }, icon(isPii ? 'shield' : severity.icon)),
            h('div', null,
                h('div', { class: 'row' }, h('strong', null, this.vocab.validationField(entry.field)), badge(severity.label, severity.variant)),
                entry.message ? h('p', { class: 'small', style: { marginTop: '4px', color: 'var(--text-2)' } }, entry.message) : null,
                corrected
                    ? h('div', { class: 'finding__change' }, h('del', null, original), icon('arrowRight'), h('ins', null, corrected))
                    : original && !entry.message ? h('div', { class: 'finding__change muted' }, original) : null));
    }

    // ── İşlem kaydı ──────────────────────────────────────

    renderTrace() {
        const timings = this.result.step_timings || [];
        const logs = this.result.agent_logs || [];
        const max = Math.max(0.1, ...timings.map((t) => t.duration || 0));
        const statusVariant = { failed: 'warning', skipped: '' };

        const bars = timings.length
            ? h('div', null, timings.map((t) => h('div', { class: 'bar-row' },
                h('span', { class: 'row' }, h('strong', null, t.label || t.step),
                    t.status && t.status !== 'completed' ? badge(t.status === 'failed' ? 'Başarısız' : 'Atlandı', statusVariant[t.status]) : null),
                meter((t.duration || 0) / max, t.status === 'failed' ? 'warning' : ''),
                h('span', { class: 'bar-row__value', title: t.agent }, fmt.seconds(t.duration)))))
            : h('p', { class: 'muted' }, 'Adım süresi kaydı yok.');

        const console = h('div', { class: 'log-console', role: 'log', 'aria-label': 'Agent işlem kayıtları' },
            logs.length ? logs.map((line) => {
                const match = /^\[(\d{2}:\d{2}:\d{2})\] \[([^\]]+)\] (.*)$/.exec(line);
                return match
                    ? h('div', { class: 'log-console__line' }, h('span', { class: 'log-console__time' }, match[1]), ' ', h('span', { class: 'log-console__agent' }, match[2]), ' ', match[3])
                    : h('div', { class: 'log-console__line' }, line);
            }) : 'Kayıt bulunamadı.');

        return h('div', { class: 'stack' },
            h('div', null, sectionTitle('clock', 'Adım süreleri', h('span', { class: 'muted small' }, ` · toplam ${fmt.seconds(this.result.processing_time)}`)), bars),
            h('div', null, sectionTitle('terminal', 'Agent kayıtları'), console),
        );
    }

    // ── Eylemler ─────────────────────────────────────────

    exportJson() {
        const payload = { ...this.result, review: this.review.state };
        downloadBlob(JSON.stringify(payload, null, 2), `analiz_${this.historyId || 'sonuc'}.json`);
    }
}

const FIELD_NAME_LABELS = { tarih: 'Tarih', sayi: 'Sayı', konu: 'Konu', imza: 'İmza / kapanış' };

function fieldLabel(code) {
    if (FIELD_NAME_LABELS[code]) return FIELD_NAME_LABELS[code];
    const text = String(code || '').replace(/_/g, ' ');
    return text.charAt(0).toLocaleUpperCase('tr-TR') + text.slice(1);
}
