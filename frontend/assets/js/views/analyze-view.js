import { ApiError } from '../core/api.js';
import { badge, emptyState, h, icon, replace, storage } from '../core/dom.js';
import { fmt } from '../core/vocabulary.js';
import { ResultView } from './result-view.js';

const SAMPLE_DOCUMENT = `T.C.
ÖRNEK İLÇE BELEDİYE BAŞKANLIĞINA

Konu: Kaldırım ve yol onarımı talebi

Yeni Mahalle, Çınar Sokak üzerinde bulunan kaldırımlar uzun süredir bozuk durumdadır. Özellikle yaşlı vatandaşlarımız ve çocuklar yürürken düşme tehlikesi yaşamakta, yağışlı havalarda su birikintileri oluşmaktadır. Daha önce yaptığım sözlü müracaat sonuçsuz kalmıştır.

Bu dilekçe ile talebim, konunun yerinde incelenerek gerekli onarım çalışmasının en kısa sürede yapılmasıdır. Başvurumun değerlendirilmesini saygılarımla arz ederim.

Ek: Fotoğraflar (3 adet)

Ad Soyad: Ayşe Yılmaz
Adres: Yeni Mahalle, Çınar Sokak No: 12, Örnek İlçe
Tarih: 14.10.2026`;

// Yazılmamış metin, sekme yenilense de kaybolmasın (yalnızca bu tarayıcı oturumunda tutulur).
function readSession(key) {
    try { return sessionStorage.getItem(key) || ''; } catch { return ''; }
}

function writeSession(key, value) {
    try { sessionStorage.setItem(key, value); } catch { /* depolama kapalı olabilir */ }
}

/** /api/jobs/{id} uç noktasını iş bitene kadar sorgular. */
class JobPoller {
    constructor(api, { interval = 800, maxNetworkErrors = 5 } = {}) {
        this.api = api;
        this.interval = interval;
        this.maxNetworkErrors = maxNetworkErrors;
    }

    async wait(jobId, onUpdate, signal) {
        let networkErrors = 0;
        for (;;) {
            if (signal?.aborted) throw new DOMException('İptal edildi', 'AbortError');
            try {
                const job = await this.api.job(jobId, signal);
                networkErrors = 0;
                onUpdate(job);
                if (job.status === 'completed' || job.status === 'failed') return job;
            } catch (error) {
                if (error.name === 'AbortError' || !(error instanceof ApiError) || error.code !== 'network') throw error;
                if (++networkErrors >= this.maxNetworkErrors) throw error;
            }
            await new Promise((resolve) => setTimeout(resolve, this.interval));
        }
    }
}

/** Sol paneldeki evrak/metin girişi. */
class InputPanel {
    constructor({ vocab, onSubmit }) {
        this.vocab = vocab;
        this.onSubmit = onSubmit;
        this.mode = storage.get('inputMode', 'file') === 'text' ? 'text' : 'file';
        this.file = null;
        this.element = this.build();
        this._autoSaveTimer = null;
        this.setMode(this.mode);
    }

    build() {
        const { limits } = this.vocab;

        this.fileTab = h('button', { type: 'button', role: 'tab', id: 'modeFile', 'aria-controls': 'filePane', onClick: () => this.setMode('file') }, icon('upload'), 'Dosya yükle');
        this.textTab = h('button', { type: 'button', role: 'tab', id: 'modeText', 'aria-controls': 'textPane', onClick: () => this.setMode('text') }, icon('type'), 'Metin yapıştır');

        // Dosya
        this.fileInput = h('input', { type: 'file', class: 'sr-only', id: 'fileInput', accept: this.vocab.acceptAttribute, tabindex: -1,
            onChange: (e) => e.target.files[0] && this.selectFile(e.target.files[0]) });
        this.dropzone = h('div', {
            class: 'dropzone', role: 'button', tabindex: 0, 'aria-describedby': 'fileHint',
            onClick: () => this.fileInput.click(),
            onKeydown: (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); this.fileInput.click(); } },
        },
            h('div', { class: 'dropzone__icon' }, icon('upload')),
            h('strong', null, 'Dosyayı buraya sürükleyin'),
            h('span', { class: 'muted' }, 'veya ', h('span', { class: 'link' }, 'bilgisayarınızdan seçin')),
            h('span', { class: 'field__hint', id: 'fileHint' }, `${this.vocab.extensionsText} · en fazla ${limits.max_file_mb} MB`),
        );
        ['dragenter', 'dragover'].forEach((type) => this.dropzone.addEventListener(type, (e) => { e.preventDefault(); this.dropzone.classList.add('is-dragover'); }));
        ['dragleave', 'drop'].forEach((type) => this.dropzone.addEventListener(type, (e) => { e.preventDefault(); this.dropzone.classList.remove('is-dragover'); }));
        this.dropzone.addEventListener('drop', (e) => e.dataTransfer.files[0] && this.selectFile(e.dataTransfer.files[0]));

        this.fileChip = h('div', { class: 'file-chip', hidden: true });
        this.fileError = h('p', { class: 'field__error', role: 'alert', hidden: true });
        this.filePane = h('div', { id: 'filePane', role: 'tabpanel', 'aria-labelledby': 'modeFile', class: 'stack-sm' },
            this.dropzone, this.fileChip, this.fileInput, this.fileError);

        // Metin
        this.titleInput = h('input', { class: 'input', id: 'docTitle', maxlength: 200, placeholder: 'Örn. Kaldırım onarımı dilekçesi', value: readSession('draftTitle') });
        this.textInput = h('textarea', {
            class: 'textarea', id: 'analyzeTextInput', placeholder: 'Evrak metnini buraya yapıştırın…', 'aria-describedby': 'textCounter',
            value: readSession('draftText'),
            onInput: () => this.onTextInput(),
            onKeydown: (e) => { if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); this.submit(); } },
        });
        this.counter = h('span', { class: 'field__hint', id: 'textCounter', 'aria-live': 'polite' });
        this.textError = h('p', { class: 'field__error', role: 'alert', hidden: true });
        this.textPane = h('div', { id: 'textPane', role: 'tabpanel', 'aria-labelledby': 'modeText', class: 'stack' },
            h('div', { class: 'field' }, h('label', { class: 'field__label', for: 'docTitle' }, 'Başlık ', h('span', { class: 'muted' }, '(isteğe bağlı)')), this.titleInput),
            h('div', { class: 'field' },
                h('div', { class: 'row row--between' },
                    h('label', { class: 'field__label', for: 'docText' }, 'Evrak metni'),
                    h('button', { type: 'button', class: 'btn btn--ghost btn--sm', onClick: () => this.loadSample() }, icon('sparkles'), 'Örnek evrak')),
                h('label', { for: 'analyzeTextInput', class: 'sr-only' }, 'Analiz edilecek metin'),
                this.textInput,
                h('div', { class: 'row row--between' }, this.counter, h('span', { class: 'field__hint' }, h('span', { class: 'kbd' }, 'Ctrl'), ' + ', h('span', { class: 'kbd' }, 'Enter'), ' ile gönder')),
                this.textError),
        );
        this.onTextInput();

        this.submitButton = h('button', { type: 'button', class: 'btn btn--primary btn--lg btn--block', onClick: () => this.submit() });
        this.setBusy(false);

        return h('section', { class: 'card', 'aria-labelledby': 'inputTitle' },
            h('div', { class: 'card__header' }, 
                h('h2', { class: 'card__title', id: 'inputTitle' }, icon('file'), 'Yeni analiz'),
                h('button', { type: 'button', class: 'btn btn--ghost btn--sm', title: 'Yazdır', onClick: () => window.print() }, icon('printer'), ' Yazdır')
            ),
            h('div', { class: 'card__body stack' },
                h('div', { class: 'segmented', role: 'tablist', 'aria-label': 'Girdi türü' }, this.fileTab, this.textTab),
                this.filePane, this.textPane, this.submitButton),
            h('div', { class: 'card__footer small muted row', style: { alignItems: 'flex-start', flexWrap: 'nowrap' } },
                icon('shield'),
                this.vocab.limits.keep_uploads
                    ? 'Kişisel veriler KVKK kapsamında otomatik işaretlenir.'
                    : 'Yüklenen dosyalar analizden sonra sunucudan silinir; kişisel veriler KVKK kapsamında otomatik işaretlenir.'),
        );
    }

    setMode(mode) {
        this.mode = mode;
        storage.set('inputMode', mode);
        const isFile = mode === 'file';
        this.fileTab.setAttribute('aria-selected', String(isFile));
        this.textTab.setAttribute('aria-selected', String(!isFile));
        this.filePane.hidden = !isFile;
        this.textPane.hidden = isFile;
    }

    selectFile(file) {
        const { limits } = this.vocab;
        const extension = `.${file.name.split('.').pop()}`.toLowerCase();
        if (!limits.allowed_extensions.includes(extension)) {
            return this.showError(this.fileError, `Bu dosya türü desteklenmiyor. Desteklenen türler: ${this.vocab.extensionsText}.`);
        }
        if (file.size > limits.max_file_mb * 1024 * 1024) {
            return this.showError(this.fileError, `Dosya ${fmt.fileSize(file.size)}; en fazla ${limits.max_file_mb} MB yüklenebilir.`);
        }
        if (file.size === 0) {
            return this.showError(this.fileError, 'Seçilen dosya boş.');
        }
        this.file = file;
        this.showError(this.fileError, null);
        replace(this.fileChip,
            h('span', { class: 'file-chip__icon' }, icon('file')),
            h('div', { class: 'grow' }, h('div', { class: 'file-chip__name', title: file.name }, file.name), h('div', { class: 'small muted' }, fmt.fileSize(file.size))),
            h('button', { type: 'button', class: 'btn btn--ghost btn--icon btn--sm', 'aria-label': 'Dosyayı kaldır', onClick: () => this.clearFile() }, icon('x')));
        this.fileChip.hidden = false;
        this.dropzone.hidden = true;
    }

    clearFile() {
        this.file = null;
        this.fileInput.value = '';
        this.fileChip.hidden = true;
        this.dropzone.hidden = false;
        this.dropzone.focus();
    }

    onTextInput() {
        const { min_text_chars: min, max_text_chars: max } = this.vocab.limits;
        const length = this.textInput.value.trim().length;
        this.counter.textContent = `${fmt.number(length)} / ${fmt.number(max)} karakter`;
        this.counter.style.color = length > max ? 'var(--danger)' : '';
        if (length >= min) this.showError(this.textError, null);
        writeSession('draftText', this.textInput.value);
        writeSession('draftTitle', this.titleInput.value);
    }

    loadSample() {
        this.textInput.value = SAMPLE_DOCUMENT;
        this.titleInput.value = 'Örnek: Kaldırım onarımı dilekçesi';
        this.onTextInput();
        this.textInput.focus();
    }

    showError(target, message) {
        target.hidden = !message;
        replace(target, message ? [icon('alert'), message] : []);
        const field = target === this.fileError ? this.dropzone : this.textInput;
        if (message) field.setAttribute('aria-invalid', 'true'); else field.removeAttribute('aria-invalid');
        return false;
    }

    /** Doğrulanmış girdiyi döndürür; geçersizse hatayı gösterip null döner. */
    collect() {
        if (this.mode === 'file') {
            if (!this.file) { this.showError(this.fileError, 'Analiz için bir dosya seçin.'); this.dropzone.focus(); return null; }
            return { kind: 'file', file: this.file, label: this.file.name };
        }
        const { min_text_chars: min, max_text_chars: max } = this.vocab.limits;
        const text = this.textInput.value.trim();
        if (text.length < min) { this.showError(this.textError, `Metin en az ${min} karakter olmalıdır.`); this.textInput.focus(); return null; }
        if (text.length > max) { this.showError(this.textError, `Metin en fazla ${fmt.number(max)} karakter olabilir.`); this.textInput.focus(); return null; }
        const title = this.titleInput.value.trim();
        return { kind: 'text', text, title, label: title || 'Metin girişi' };
    }

    submit() {
        if (this.busy) return;
        const input = this.collect();
        if (input) this.onSubmit(input);
    }

    setBusy(busy) {
        this.busy = busy;
        this.submitButton.disabled = busy;
        replace(this.submitButton, busy ? [icon('loader', 'spin'), 'Analiz ediliyor…'] : [icon('sparkles'), 'Analiz et']);
    }
}

/** Çalışan işin adım adım ilerlemesi. */
class ProgressPanel {
    constructor(steps) {
        this.steps = steps;
    }

    render(label) {
        this.startedAt = Date.now();
        this.items = new Map();
        this.elapsed = h('span', { class: 'muted small', style: { fontVariantNumeric: 'tabular-nums' } }, '0 sn');
        this.bar = h('div', { class: 'progress-bar__fill', style: { width: '0%' } });
        this.status = h('p', { class: 'sr-only', 'aria-live': 'polite' });
        const list = h('ol', { class: 'progress-steps' }, this.steps.map((step) => {
            const item = h('li', { class: 'progress-step', dataset: { status: 'pending' } },
                h('span', { class: 'progress-step__icon' }, icon('minus')),
                h('span', { class: 'progress-step__label' }, step.label),
                h('span', { class: 'progress-step__time' }));
            this.items.set(step.key, item);
            return item;
        }));
        clearInterval(this.timer);
        this.timer = setInterval(() => { this.elapsed.textContent = fmt.seconds(Math.round((Date.now() - this.startedAt) / 1000)); }, 1000);

        return h('section', { class: 'card card__body stack', 'aria-labelledby': 'progressTitle', 'aria-busy': 'true' },
            h('div', { class: 'row row--between' },
                h('div', null,
                    h('h2', { class: 'card__title', id: 'progressTitle' }, icon('loader', 'spin'), 'Evrak analiz ediliyor'),
                    h('p', { class: 'muted small', style: { marginTop: '4px' } }, label)),
                this.elapsed),
            h('div', { class: 'progress-bar', role: 'progressbar', 'aria-label': 'Analiz ilerlemesi' }, this.bar),
            list,
            this.status,
            h('p', { class: 'small muted' }, 'Yapay zekâ adımları birkaç saniye ile birkaç dakika arasında sürebilir. Bu sırada diğer sayfalara geçebilirsiniz; analiz arka planda devam eder.'),
        );
    }

    update(job) {
        let done = 0;
        for (const step of job.steps || []) {
            const item = this.items.get(step.key);
            if (!item) continue;
            if (item.dataset.status !== step.status) {
                item.dataset.status = step.status;
                const iconName = { running: 'loader', completed: 'check', failed: 'alert', skipped: 'minus' }[step.status] || 'minus';
                item.querySelector('.progress-step__icon').replaceChildren(icon(iconName, step.status === 'running' ? 'spin' : ''));
                if (step.status === 'running') this.status.textContent = `${item.querySelector('.progress-step__label').textContent} çalışıyor`;
            }
            item.querySelector('.progress-step__time').textContent = step.duration != null ? fmt.seconds(step.duration) : '';
            if (['completed', 'failed', 'skipped'].includes(step.status)) done += 1;
        }
        const pct = Math.round((done / this.steps.length) * 100);
        this.bar.style.width = `${pct}%`;
        this.bar.parentElement.setAttribute('aria-valuenow', pct);
    }

    stop() {
        clearInterval(this.timer);
    }
}

export class AnalyzeView {
    title = 'Analiz';

    constructor({ api, vocab, toaster, navigate }) {
        this.api = api;
        this.vocab = vocab;
        this.toaster = toaster;
        this.navigate = navigate;
        this.poller = new JobPoller(api);
        this.progress = new ProgressPanel(vocab.steps);
        this.resultView = new ResultView({ api, vocab, toaster, onNewAnalysis: () => this.reset() });
        this.input = new InputPanel({ vocab, onSubmit: (input) => this.run(input) });
        this.currentHistoryId = null;

        this.workspace = h('div', { class: 'analyze-layout__main', 'aria-live': 'polite' });
        this.element = h('div', { class: 'analyze-layout' },
            h('aside', { class: 'analyze-layout__aside' }, this.input.element),
            this.workspace);
        this.showEmpty();
    }

    async show({ id } = {}) {
        // Kimliksiz rota mevcut çalışma alanını korur; sıfırlama yalnızca "Yeni analiz" ile yapılır.
        if (id && id !== this.currentHistoryId && !this.running) await this.openRecord(id);
    }

    showEmpty() {
        this.currentHistoryId = null;
        replace(this.workspace, h('section', { class: 'card' },
            emptyState({
                iconName: 'sparkles',
                title: 'Evrakınızı analiz etmeye hazır',
                text: 'Soldan bir evrak yükleyin veya metnini yapıştırın. Sistem; sınıflandırma, mevzuat eşleştirme, resmî yazı taslağı ve birim yönlendirmesini sizin için hazırlar.',
                action: h('div', { class: 'stack', style: { alignItems: 'center', width: '100%' } },
                    h('ol', { class: 'how-it-works' },
                        [['Yükleyin', 'PDF, görüntü veya metin evrakı ekleyin.'],
                         ['İnceleyin', 'Yapay zekâ ajanları evrakı analiz eder, kural motoru doğrular.'],
                         ['Onaylayın', 'Taslak yazıyı ve yönlendirmeyi onaylayın veya düzenleyin.']]
                            .map(([title, text], i) => h('li', null, h('span', { class: 'step-no' }, i + 1), h('strong', null, title), h('span', { class: 'small' }, text)))),
                    h('button', { type: 'button', class: 'btn btn--secondary', onClick: () => { this.input.setMode('text'); this.input.loadSample(); } }, icon('file'), 'Örnek evrakla dene')),
            })));
    }

    reset() {
        this.navigate('#/analiz');
        this.showEmpty();
        (this.input.mode === 'file' ? this.input.dropzone : this.input.textInput).focus();
    }

    async run(input) {
        this.lastInput = input;
        this.running = true;
        this.input.setBusy(true);
        replace(this.workspace, this.progress.render(input.label));
        try {
            const { job_id: jobId } = input.kind === 'file'
                ? await this.api.startFileJob(input.file)
                : await this.api.startTextJob(input.text, input.title);
            const job = await this.poller.wait(jobId, (update) => this.progress.update(update));
            if (job.status === 'failed') throw new ApiError(job.error?.detail || 'Analiz tamamlanamadı.', { code: job.error?.code });

            const result = job.result;
            this.showResult(result, result.history_id, result.review);
            this.toaster.success(result.status === 'partial' ? 'Analiz kısmen tamamlandı; uyarıları inceleyin.' : `Analiz tamamlandı: ${input.label}`);
            // Kullanıcı başka sayfadaysa onu zorla geri çekme; sonuç Analiz sekmesinde hazır bekler.
            if (this.element.isConnected) this.navigate(`#/analiz/${result.history_id}`);
        } catch (error) {
            this.showError(error);
        } finally {
            this.progress.stop();
            this.running = false;
            this.input.setBusy(false);
        }
    }

    async openRecord(id) {
        replace(this.workspace, h('section', { class: 'card' }, emptyState({ iconName: 'loader', title: 'Kayıt yükleniyor…', compact: true })));
        try {
            const record = await this.api.historyRecord(id);
            this.showResult(record.result || record, record.id, record.review);
        } catch (error) {
            this.currentHistoryId = null;
            replace(this.workspace, h('section', { class: 'card' }, emptyState({
                iconName: 'alert', title: 'Kayıt açılamadı', text: error.message,
                action: h('button', { type: 'button', class: 'btn btn--secondary', onClick: () => this.reset() }, 'Yeni analiz başlat'),
            })));
        }
    }

    showResult(result, historyId, review) {
        this.currentHistoryId = historyId;
        replace(this.workspace, this.resultView.render(result, { historyId, review }));
    }

    showError(error) {
        const retry = h('button', { type: 'button', class: 'btn btn--primary', onClick: () => this.run(this.lastInput) }, icon('refresh'), 'Tekrar dene');
        const hint = {
            llm_unavailable: 'Yapay zekâ servisine ulaşılamadı veya kota doldu. Birkaç dakika sonra tekrar deneyin.',
            llm_auth_error: 'Sunucudaki LLM API anahtarı geçersiz. Sistem yöneticinize başvurun.',
            text_extraction_failed: 'Dosya taranmış bir görüntüyse daha net bir kopya deneyin veya metni yapıştırın.',
            network: 'Sunucu bağlantısı kesildi. Sunucunun çalıştığından emin olun.',
            pipeline_timeout: 'Analiz süresi aşıldı. Daha kısa bir metin veya daha küçük bir dosya deneyin.',
            circuit_breaker_open: 'Yapay zekâ servisi art arda hatalar nedeniyle geçici olarak devre dışı. Birkaç dakika bekleyip tekrar deneyin.',
        }[error.code];
        replace(this.workspace, h('section', { class: 'card card__body stack' },
            h('div', { class: 'alert alert--danger', role: 'alert' }, icon('circleX'),
                h('div', null, h('strong', null, 'Analiz tamamlanamadı'), error.message || 'Beklenmeyen bir hata oluştu.')),
            hint ? h('p', { class: 'muted' }, hint) : null,
            h('div', { class: 'row' }, retry,
                h('button', { type: 'button', class: 'btn btn--ghost', onClick: () => this.reset() }, 'Vazgeç')),
            error.code ? h('p', { class: 'small muted' }, 'Hata kodu: ', badge(error.code)) : null,
        ));
        retry.focus();
    }
}
