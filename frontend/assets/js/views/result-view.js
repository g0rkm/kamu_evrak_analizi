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
    if (score >= 0.8) return 'Yüksek düzey: sonuçlar kendi içinde tutarlı.';
    if (score >= 0.5) return 'Orta düzey: sistem bu sonuçtan tam emin değil. Lütfen evrak türünü ve birimi kontrol edin.';
    return 'Düşük düzey: sonuçları göndermeden önce elle kontrol edin.';
}

function panel(label, ...children) {
    return h('div', { class: 'panel' }, h('div', { class: 'panel__label' }, label), ...children);
}

export class ResultView {
    constructor({ api, vocab, toaster, onNewAnalysis }) {
        this.api = api;
        this.vocab = vocab;
        this.toaster = toaster;
        this.onNewAnalysis = onNewAnalysis;
        this.activeTab = 'content';
    }

    render(result, { historyId = null, review = null } = {}) {
        if (historyId !== this.historyId) this.activeTab = 'content';
        this.result = result;
        this.historyId = historyId;
        this.review = new ReviewController({ api: this.api, toaster: this.toaster, historyId, review });

        const validation = result.validation || [];
        this.piiEntries = validation.filter((v) => v.field?.startsWith('pii.'));
        this.leakEntries = validation.filter((v) => v.field?.startsWith('draft_pii_leak.'));
        const attention = validation.filter((v) => v.severity !== 'info').length;
        const analysis = result.analysis || {};

        this.tabSubscriptions = [];
        const scoped = (render) => () => {
            this.tabSubscriptions.forEach((unsubscribe) => unsubscribe());
            this.tabSubscriptions = [];
            return render();
        };

        const tabs = new Tabs([
            { id: 'content', label: 'İçerik', icon: 'network', count: (analysis.missing_fields || []).length || null, countVariant: 'warning', render: scoped(() => this.renderContent()) },
            { id: 'legislation', label: 'Mevzuat', icon: 'scale', count: (analysis.legislation_matches || []).length || null, render: scoped(() => this.renderLegislation()) },
            { id: 'routing', label: 'Yönlendirme', icon: 'route', render: scoped(() => this.renderRouting()) },
            { id: 'validation', label: 'Doğrulama', icon: 'shieldCheck', count: attention || null, countVariant: 'warning', render: scoped(() => this.renderValidation()) },
            { id: 'trace', label: 'İşlem kaydı', icon: 'terminal', render: scoped(() => this.renderTrace()) },
        ], { initial: this.activeTab, onChange: (id) => { this.activeTab = id; } });

        const detailsToggle = h('details', { class: 'card', style: { padding: '18px 22px' } },
            h('summary', { style: { cursor: 'pointer', fontFamily: 'var(--font-heading)', fontSize: '18px' } },
                'Ayrıntılı inceleme (varlıklar, mevzuat, yönlendirme, doğrulama)'),
            tabs.element);

        return h('div', { style: { display: 'flex', flexDirection: 'column', gap: '24px' } },
            result.status === 'partial' ? this.renderPartialWarning() : null,
            this.renderStageDone(),
            detailsToggle);
    }

    // ── Tasarımdaki iki sütunlu sonuç görünümü ───────────

    renderStageDone() {
        const { result, vocab } = this;
        const analysis = result.analysis || {};
        const classification = analysis.classification || {};
        const routing = result.routing || {};
        const matches = analysis.legislation_matches || [];
        const score = result.confidence_score || 0;
        const pct = Math.round(score * 100);

        const docTypeText = vocab.documentType(classification.document_type)
            + (classification.sub_type ? ` (${classification.sub_type})` : '');
        const prioText = routing.priority ? vocab.priority(routing.priority) : 'Normal';
        const unitSpan = h('span', null, this.currentUnit() || '—');
        this.review.subscribe(() => { unitSpan.textContent = this.currentUnit() || '—'; });
        const legText = matches.length ? matches.map((m) => m.legislation_name).join(', ') : 'Belirtilmedi';

        const leftCol = h('div', { style: { display: 'flex', flexDirection: 'column', gap: '16px' } },
            h('div', { class: 'card', style: { padding: '22px', gap: '14px' } },
                h('div', { class: 'card-kicker' }, 'Sonuç özeti'),
                h('div', { style: { fontFamily: 'var(--font-heading)', fontSize: '22px', lineHeight: 1.2, overflowWrap: 'anywhere' } },
                    result.source_name || 'İncelenen evrak'),
                h('div', { style: { display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '8px 16px', fontSize: '14px' } },
                    h('span', { style: { color: 'var(--color-neutral-700)' } }, 'Evrak türü'), h('span', null, docTypeText),
                    h('span', { style: { color: 'var(--color-neutral-700)' } }, 'Öncelik'), h('span', null, prioText),
                    h('span', { style: { color: 'var(--color-neutral-700)' } }, 'Gönderilecek birim'), unitSpan,
                    h('span', { style: { color: 'var(--color-neutral-700)' } }, 'İlgili mevzuat'), h('span', null, legText))),
            h('div', { class: 'card', style: { padding: '22px', gap: '10px' } },
                h('div', { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' } },
                    h('div', { class: 'card-kicker' }, 'Sistemin eminlik düzeyi'),
                    h('span', { style: { fontFamily: 'var(--font-heading)', fontSize: '24px', fontVariantNumeric: 'tabular-nums' } }, `%${pct}`)),
                h('div', { style: { height: '5px', background: 'var(--color-neutral-200)', borderRadius: '3px', overflow: 'hidden' } },
                    h('div', { style: { width: `${pct}%`, height: '100%', background: 'var(--color-accent)' } })),
                h('p', { style: { margin: 0, fontSize: '13px', color: 'var(--color-neutral-800)', textWrap: 'pretty' } }, confidenceText(score))),
            h('div', { class: 'card', style: { padding: '22px', gap: '8px' } },
                h('div', { class: 'card-kicker' }, 'Kısa özet'),
                h('p', { style: { margin: 0, fontSize: '14px', textAlign: 'justify', hyphens: 'auto' } },
                    analysis.summary || 'Bu evrak için özet metin üretilemedi.')));

        return h('div', { class: 'split', style: { display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1.5fr)', gap: '24px', alignItems: 'start' } },
            leftCol,
            this.renderDraftCard());
    }

    renderDraftCard() {
        const draft = this.result.draft;
        const statusTag = h('span', { class: 'tag tag-outline' }, 'Onayınızı bekliyor');
        const body = h('div', { class: 'letter__body', style: { whiteSpace: 'pre-wrap' } }, this.draftBody());
        const today = new Date(this.result.created_at || Date.now()).toLocaleDateString('tr-TR');

        const letter = draft
            ? h('article', { class: 'letter', 'aria-label': 'Hazırlanan cevap yazısı taslağı' }, body)
            : h('div', { class: 'letter' }, 'Bu evrak için cevap yazısı taslağı üretilemedi.');

        const editor = h('div', { class: 'stack-sm', hidden: true });
        const actions = h('div', { style: { display: 'flex', gap: '10px', justifyContent: 'flex-end', flexWrap: 'wrap' } });

        const syncBar = () => {
            const status = this.review.state.draft_status || 'pending';
            const info = DRAFT_STATUS[status] || DRAFT_STATUS.pending;
            statusTag.textContent = status === 'pending' ? 'Onayınızı bekliyor' : info.label;
            statusTag.className = status === 'approved' ? 'tag tag-accent' : 'tag tag-outline';
            body.textContent = this.draftBody();

            replace(actions,
                h('button', { type: 'button', class: 'btn btn-ghost', onClick: () => this.onNewAnalysis?.() }, 'Yeni evrak'),
                draft ? h('button', { type: 'button', class: 'btn btn-secondary', onClick: () => this.openEditor(letter, editor) }, 'Düzenle') : null,
                h('button', { type: 'button', class: 'btn btn-secondary', onClick: () => window.print() }, 'Yazdır'),
                draft && status !== 'approved'
                    ? h('button', {
                        type: 'button', class: 'btn btn-primary', style: { padding: '10px 22px' },
                        onClick: () => this.review.update({ draft_status: 'approved' }, 'Taslak onaylandı.'),
                    }, 'Taslağı onayla')
                    : draft
                        ? h('button', {
                            type: 'button', class: 'btn btn-secondary',
                            onClick: () => this.review.update({ draft_status: 'pending', reject_reason: null }),
                        }, 'Onayı geri al')
                        : null);
        };
        syncBar();
        this.review.subscribe(syncBar);

        return h('div', { class: 'card', style: { padding: '28px', gap: '16px' } },
            h('div', { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '12px', flexWrap: 'wrap' } },
                h('div', null,
                    h('div', { class: 'card-kicker' }, 'Hazırlanan cevap yazısı taslağı'),
                    h('div', { style: { fontSize: '12px', color: 'var(--color-neutral-700)' } }, 'Göndermeden önce okuyup düzenleyebilirsiniz.')),
                statusTag),
            this.leakEntries.length ? h('div', { class: 'alert alert--danger' }, icon('shield'),
                h('div', null, h('strong', null, 'Taslakta kişisel veri tespit edildi'),
                    this.leakEntries.map((e) => `${this.vocab.piiLabel(e.field.split('.')[1])} (${e.original_value})`).join(', '))) : null,
            editor,
            letter,
            actions);
    }

    renderPartialWarning() {
        return h('div', { class: 'alert alert--warning', role: 'status' }, icon('alert'),
            h('div', null,
                h('strong', null, 'Analiz kısmen tamamlandı'),
                'Bazı adımlar başarısız oldu; bu bölümlerde varsayılan değerler gösteriliyor.',
                h('ul', null, (this.result.warnings || []).map((w) => h('li', null, w)))));
    }

    draftBody() {
        return this.review.state.draft_body ?? this.result.draft?.rendered_text ?? this.result.draft?.body ?? '';
    }

    openEditor(letter, editor) {
        const textarea = h('textarea', { class: 'input', id: 'draftEditor', value: this.draftBody(), style: { minHeight: '260px', fontSize: '14px', lineHeight: 1.7 } });
        const close = () => { editor.hidden = true; letter.hidden = false; editor.replaceChildren(); };
        replace(editor,
            h('div', { class: 'field' }, h('label', { for: 'draftEditor' }, 'Taslak metnini düzenleyin'), textarea),
            h('div', { class: 'row' },
                h('button', {
                    type: 'button', class: 'btn btn-primary',
                    onClick: async () => { if (await this.review.update({ draft_status: 'edited', draft_body: textarea.value }, 'Düzenlenen taslak kaydedildi.')) close(); },
                }, 'Kaydet'),
                h('button', { type: 'button', class: 'btn btn-secondary', onClick: () => this.maskDraftPii(textarea) }, 'Kişisel verileri gizle'),
                h('button', { type: 'button', class: 'btn btn-ghost', onClick: close }, 'Vazgeç')));
        letter.hidden = true;
        editor.hidden = false;
        textarea.focus();
    }

    async maskDraftPii(textarea) {
        try {
            const { masked_text, pii_count } = await this.api.maskPii(textarea.value);
            if (pii_count === 0) {
                this.toaster.info('Taslakta kişisel veri bulunamadı.');
                return;
            }
            textarea.value = masked_text;
            this.toaster.success(`${pii_count} kişisel veri maskelendi.`);
        } catch (error) {
            this.toaster.error(`Maskeleme başarısız: ${error.message}`);
        }
    }

    // ── Ayrıntı sekmeleri ────────────────────────────────

    renderContent() {
        const analysis = this.result.analysis || {};
        const entities = analysis.entities || [];
        const missing = analysis.missing_fields || [];

        const entityTable = entities.length
            ? h('div', { class: 'table-wrap' }, h('table', { class: 'table' },
                h('thead', null, h('tr', null, h('th', null, 'Tür'), h('th', null, 'Değer'), h('th', null, 'Konum'))),
                h('tbody', null, entities.map((e) => h('tr', null,
                    h('td', null, badge(this.vocab.entity(e.entity_type))),
                    h('td', null, e.value || '—'),
                    h('td', { class: 'muted small' }, e.position || '—'))))))
            : emptyState({ iconName: 'network', title: 'Varlık bulunamadı', compact: true });

        const missingList = missing.length
            ? h('ul', { class: 'list' }, missing.map((m) => h('li', { class: 'list-item' },
                h('span', { class: 'list-item__icon' }, icon('alert')),
                h('div', { class: 'grow' },
                    h('div', { class: 'row' }, h('span', { class: 'list-item__title' }, fieldLabel(m.field_name)),
                        m.is_critical ? badge('Kritik', 'danger') : badge('Önerilen', 'warning')),
                    m.description ? h('p', { class: 'small muted' }, m.description) : null))))
            : h('div', { class: 'alert alert--success' }, icon('circleCheck'), 'Eksik alan tespit edilmedi.');

        return h('div', { class: 'stack' },
            h('div', null, h('div', { class: 'card-kicker', style: { marginBottom: '8px' } }, 'Çıkarılan bilgiler'), entityTable),
            h('div', null, h('div', { class: 'card-kicker', style: { marginBottom: '8px' } }, 'Eksik alanlar'), missingList));
    }

    renderLegislation() {
        const matches = this.result.analysis?.legislation_matches || [];
        if (!matches.length) {
            return emptyState({ iconName: 'scale', title: 'Eşleşen mevzuat bulunamadı', text: 'Evrak metniyle ilişkilendirilebilecek bir mevzuat tespit edilmedi.', compact: true });
        }
        return h('div', { class: 'stack-sm' }, matches.map((m) => h('article', { class: 'legislation-card' },
            h('div', { class: 'row row--between' },
                h('h4', null, m.legislation_name, m.article ? h('span', { class: 'muted small' }, ` · Madde ${String(m.article).replace(/^madde\s*/i, '')}`) : null),
                badge(`İlgi ${fmt.percent(m.relevance_score)}`, 'primary')),
            meter(m.relevance_score),
            m.summary ? h('p', { class: 'small', style: { margin: 0 } }, m.summary) : null)));
    }

    currentUnit() {
        return this.review.state.routing_unit || this.result.routing?.target_unit || '';
    }

    renderRouting() {
        const routing = this.result.routing;
        if (!routing) {
            return emptyState({ iconName: 'route', title: 'Yönlendirme yapılamadı', text: 'Bu evrak için birim önerisi üretilemedi.', compact: true });
        }
        const unitText = h('p', { style: { fontFamily: 'var(--font-heading)', fontSize: '20px', margin: 0 } }, this.currentUnit());
        const reviewBar = h('div', { class: 'review-bar', style: { justifyContent: 'flex-start' } });
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
                panel('Hedef birim', unitText),
                panel('Öncelik', badge(this.vocab.priority(routing.priority), this.vocab.priorityVariant(routing.priority), 'badge--lg'))),
            panel('Gerekçe', h('p', { style: { margin: 0 } }, routing.reasoning || 'Gerekçe belirtilmedi.')),
            h('div', { class: 'grid-2' },
                panel('Alternatif birimler', alternatives.length ? h('div', { class: 'chips' }, alternatives.map((u) => h('span', { class: 'chip' }, u))) : h('p', { class: 'muted', style: { margin: 0 } }, 'Alternatif önerilmedi.')),
                panel('Birimden beklenen eylemler', actions.length
                    ? h('ul', { class: 'list' }, actions.map((a) => h('li', { class: 'list-item' }, a)))
                    : h('p', { class: 'muted', style: { margin: 0 } }, 'Belirtilmiş bir eylem yok.'))));
    }

    routingReviewControls(changeArea) {
        const status = this.review.state.routing_status || 'pending';
        const info = ROUTING_STATUS[status] || ROUTING_STATUS.pending;
        const controls = [h('span', { class: 'row grow' }, h('strong', null, 'Yönlendirme kararı:'), badge(info.label, info.variant))];
        if (status === 'pending') {
            controls.push(
                h('button', { type: 'button', class: 'btn btn-primary btn--sm', onClick: () => this.review.update({ routing_status: 'approved' }, 'Yönlendirme onaylandı.') }, 'Onayla'),
                h('button', { type: 'button', class: 'btn btn-secondary btn--sm', onClick: () => this.openUnitChooser(changeArea) }, 'Birimi değiştir'));
        } else {
            controls.push(h('button', {
                type: 'button', class: 'btn btn-ghost btn--sm',
                onClick: () => this.review.update({ routing_status: 'pending', routing_unit: null }),
            }, 'Kararı geri al'));
        }
        return controls;
    }

    openUnitChooser(area) {
        const current = this.currentUnit();
        const select = h('select', { class: 'input', id: 'unitSelect' },
            h('option', { value: '' }, 'Birim seçin…'),
            this.vocab.units.map((u) => h('option', { value: u.label, selected: u.label === current }, u.label)));
        const close = () => { area.hidden = true; area.replaceChildren(); };
        replace(area,
            h('div', { class: 'field' }, h('label', { for: 'unitSelect' }, 'Evrakın yönlendirileceği birim'), select),
            h('div', { class: 'row' },
                h('button', {
                    type: 'button', class: 'btn btn-primary btn--sm',
                    onClick: async () => {
                        if (!select.value) { select.focus(); return; }
                        if (await this.review.update({ routing_status: 'changed', routing_unit: select.value }, 'Yönlendirme güncellendi.')) close();
                    },
                }, 'Kaydet'),
                h('button', { type: 'button', class: 'btn btn-ghost btn--sm', onClick: close }, 'Vazgeç')));
        area.hidden = false;
        select.focus();
    }

    renderValidation() {
        const validation = this.result.validation || [];
        const score = this.result.confidence_score || 0;
        const corrections = validation.filter((v) => v.severity === 'correction').length;
        const warnings = validation.filter((v) => v.severity === 'warning').length;

        const header = h('div', { class: 'panel row', style: { gap: '16px' } },
            scoreRing(score, 'Eminlik'),
            h('div', { class: 'grow' },
                h('div', { class: 'panel__label' }, 'Eminlik değerlendirmesi'),
                h('p', { style: { margin: 0 } }, confidenceText(score)),
                h('p', { class: 'small muted', style: { margin: '4px 0 0' } }, `${corrections} düzeltme · ${warnings} uyarı`)));

        const list = validation.length
            ? h('div', { class: 'stack-sm' }, validation.map((v) => this.renderFinding(v)))
            : h('div', { class: 'alert alert--success' }, icon('circleCheck'), 'Doğrulama kurallarının tamamı sorunsuz geçti.');

        return h('div', { class: 'stack' }, header, list);
    }

    renderFinding(entry) {
        const isPii = entry.field?.startsWith('pii.') || entry.field?.startsWith('draft_pii_leak.');
        const severity = SEVERITY[entry.severity] || SEVERITY.info;
        const original = this.vocab.validationValue(entry.field, entry.original_value);
        const corrected = this.vocab.validationValue(entry.field, entry.corrected_value);

        return h('div', { class: `finding finding--${entry.severity || 'info'}` },
            h('span', { class: 'finding__icon' }, icon(isPii ? 'shield' : severity.icon)),
            h('div', null,
                h('div', { class: 'row' }, h('strong', null, this.vocab.validationField(entry.field)), badge(severity.label, severity.variant)),
                entry.message ? h('p', { class: 'small', style: { margin: '4px 0 0' } }, entry.message) : null,
                corrected
                    ? h('div', { class: 'finding__change' }, h('del', null, original), icon('arrowRight'), h('ins', null, corrected))
                    : original && !entry.message ? h('div', { class: 'finding__change muted' }, original) : null));
    }

    renderTrace() {
        const timings = this.result.step_timings || [];
        const logs = this.result.agent_logs || [];
        const max = Math.max(0.1, ...timings.map((t) => t.duration || 0));

        const bars = timings.length
            ? h('div', null, timings.map((t) => h('div', { class: 'bar-row', style: { gridTemplateColumns: '180px 1fr 70px' } },
                h('span', null, t.label || t.step),
                meter((t.duration || 0) / max),
                h('span', { class: 'bar-row__value' }, fmt.seconds(t.duration)))))
            : h('p', { class: 'muted' }, 'Adım süresi kaydı yok.');

        const logBox = h('div', { class: 'log-console', role: 'log' },
            logs.length ? logs.map((line) => h('div', { class: 'log-console__line' }, line)) : 'Kayıt bulunamadı.');

        return h('div', { class: 'stack' },
            h('div', null, h('div', { class: 'card-kicker', style: { marginBottom: '8px' } }, `Adım süreleri · toplam ${fmt.seconds(this.result.processing_time)}`), bars),
            h('div', null, h('div', { class: 'card-kicker', style: { marginBottom: '8px' } }, 'Sistem kayıtları'), logBox),
            h('div', { class: 'row' },
                h('button', { type: 'button', class: 'btn btn-secondary btn--sm', onClick: () => downloadBlob(JSON.stringify({ ...this.result, review: this.review.state }, null, 2), `analiz_${this.historyId || 'sonuc'}.json`) }, 'JSON olarak indir')));
    }
}

const FIELD_NAME_LABELS = { tarih: 'Tarih', sayi: 'Sayı', konu: 'Konu', imza: 'İmza / kapanış' };

function fieldLabel(code) {
    if (FIELD_NAME_LABELS[code]) return FIELD_NAME_LABELS[code];
    const text = String(code || '').replace(/_/g, ' ');
    return text.charAt(0).toLocaleUpperCase('tr-TR') + text.slice(1);
}
