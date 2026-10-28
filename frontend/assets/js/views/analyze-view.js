import { ApiError } from '../core/api.js';
import { h, icon, replace, storage } from '../core/dom.js';
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

function readSession(key) {
    try { return sessionStorage.getItem(key) || ''; } catch { return ''; }
}

function writeSession(key, value) {
    try { sessionStorage.setItem(key, value); } catch {}
}

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

class InputCard {
    constructor({ vocab, onSubmit, onSample }) {
        this.vocab = vocab;
        this.onSubmit = onSubmit;
        this.onSample = onSample;
        this.mode = storage.get('inputMode', 'file') === 'text' ? 'text' : 'file';
        this.file = null;
        this.element = this.build();
        this.setMode(this.mode);
    }

    build() {
        const { limits } = this.vocab;

        this.fileRadio = h('input', { type: 'radio', name: 'mode', checked: this.mode === 'file', onChange: () => this.setMode('file') });
        this.textRadio = h('input', { type: 'radio', name: 'mode', checked: this.mode === 'text', onChange: () => this.setMode('text') });

        this.fileInput = h('input', {
            type: 'file', class: 'sr-only', id: 'fileInput', accept: this.vocab.acceptAttribute, tabindex: -1,
            onChange: (e) => e.target.files[0] && this.selectFile(e.target.files[0]),
        });
        this.dropzone = h('div', {
            class: 'dropzone', role: 'button', tabindex: 0, 'aria-describedby': 'fileHint',
            onClick: () => this.fileInput.click(),
            onKeydown: (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); this.fileInput.click(); } },
        },
            h('span', { class: 'dropzone__icon' }, icon('upload')),
            h('div', { class: 'dropzone__title' }, 'Dosyanızı buraya sürükleyip bırakın'),
            h('div', { style: { fontSize: '14px' } }, 'veya ', h('a', { href: '#', onClick: (e) => { e.preventDefault(); e.stopPropagation(); this.fileInput.click(); } }, 'bilgisayarınızdan seçin')),
            h('div', { id: 'fileHint', style: { fontSize: '12px', color: 'var(--color-neutral-700)' } },
                `PDF, Word, resim (JPG, PNG, TIFF) veya metin dosyası · en fazla ${limits.max_file_mb} MB`));
        ['dragenter', 'dragover'].forEach((type) => this.dropzone.addEventListener(type, (e) => { e.preventDefault(); this.dropzone.classList.add('is-dragover'); }));
        ['dragleave', 'drop'].forEach((type) => this.dropzone.addEventListener(type, (e) => { e.preventDefault(); this.dropzone.classList.remove('is-dragover'); }));
        this.dropzone.addEventListener('drop', (e) => e.dataTransfer.files[0] && this.selectFile(e.dataTransfer.files[0]));

        this.fileChip = h('div', { class: 'file-chip', hidden: true });
        this.fileError = h('p', { class: 'field__error', role: 'alert', hidden: true });
        this.filePane = h('div', { id: 'filePane' }, this.dropzone, this.fileChip, this.fileInput, this.fileError);

        this.textInput = h('textarea', {
            class: 'input', id: 'analyzeTextInput',
            placeholder: 'Evrakın metnini buraya yapıştırın…',
            style: { minHeight: '200px', fontSize: '15px' },
            value: readSession('draftText'),
            onInput: () => this.onTextInput(),
            onKeydown: (e) => { if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); this.submit(); } },
        });
        this.textError = h('p', { class: 'field__error', role: 'alert', hidden: true });
        this.textPane = h('div', { id: 'textPane', class: 'field' },
            h('label', { for: 'analyzeTextInput' }, 'Evrak metni'),
            this.textInput,
            this.textError);

        this.submitButton = h('button', {
            type: 'button', class: 'btn btn-primary', style: { fontSize: '17px', padding: '12px 34px' },
            onClick: () => this.submit(),
        }, 'Analizi başlat');

        return h('div', { class: 'card', style: { maxWidth: '720px', width: '100%', margin: '0 auto', padding: '30px', gap: '20px' } },
            h('div', { class: 'seg', style: { alignSelf: 'center' } },
                h('label', { class: 'seg-opt', style: { fontSize: '14px', padding: '9px 18px' } }, this.fileRadio, 'Dosya yükle'),
                h('label', { class: 'seg-opt', style: { fontSize: '14px', padding: '9px 18px' } }, this.textRadio, 'Metin yapıştır')),
            this.filePane,
            this.textPane,
            h('div', { style: { display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '10px' } },
                this.submitButton,
                h('button', { type: 'button', class: 'btn btn-ghost', style: { fontSize: '14px' }, onClick: () => this.onSample() }, 'Önce örnek bir evrakla deneyin')),
            h('div', { style: { display: 'flex', gap: '10px', alignItems: 'flex-start', justifyContent: 'center', borderTop: '1px solid var(--color-divider)', paddingTop: '16px', fontSize: '12px', color: 'var(--color-neutral-700)', textAlign: 'center' } },
                h('span', { style: { flex: 'none', marginTop: '2px', display: 'inline-flex' } }, icon('shield')),
                h('span', null, 'Yüklenen dosyalar analizden sonra silinir. Kişisel bilgiler KVKK kapsamında otomatik olarak işaretlenir.')));
    }

    setMode(mode) {
        this.mode = mode;
        storage.set('inputMode', mode);
        const isFile = mode === 'file';
        this.fileRadio.checked = isFile;
        this.textRadio.checked = !isFile;
        this.filePane.hidden = !isFile;
        this.textPane.hidden = isFile;
    }

    syncFromSession() {
        const saved = readSession('draftText');
        if (saved && this.textInput.value !== saved) this.textInput.value = saved;
        const savedMode = storage.get('inputMode', 'file') === 'text' ? 'text' : 'file';
        if (savedMode !== this.mode) this.setMode(savedMode);
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
            h('button', { type: 'button', class: 'btn btn-ghost btn-icon', 'aria-label': 'Dosyayı kaldır', onClick: () => this.clearFile() }, icon('x')));
        this.fileChip.hidden = false;
        this.dropzone.hidden = true;
    }

    clearFile() {
        this.file = null;
        this.fileInput.value = '';
        this.fileChip.hidden = true;
        this.dropzone.hidden = false;
    }

    onTextInput() {
        const { min_text_chars: min } = this.vocab.limits;
        if (this.textInput.value.trim().length >= min) this.showError(this.textError, null);
        writeSession('draftText', this.textInput.value);
    }

    loadSample() {
        this.setMode('text');
        this.textInput.value = SAMPLE_DOCUMENT;
        writeSession('draftTitle', 'Örnek: Kaldırım onarımı dilekçesi');
        this.onTextInput();
    }

    showError(target, message) {
        target.hidden = !message;
        replace(target, message ? [icon('alert'), message] : []);
        return false;
    }

    collect() {
        if (this.mode === 'file') {
            if (!this.file) { this.showError(this.fileError, 'Analiz için bir dosya seçin.'); return null; }
            return { kind: 'file', file: this.file, label: this.file.name };
        }
        const { min_text_chars: min, max_text_chars: max } = this.vocab.limits;
        const text = this.textInput.value.trim();
        if (text.length < min) { this.showError(this.textError, `Metin en az ${min} karakter olmalıdır.`); this.textInput.focus(); return null; }
        if (text.length > max) { this.showError(this.textError, `Metin en fazla ${fmt.number(max)} karakter olabilir.`); this.textInput.focus(); return null; }
        const title = readSession('draftTitle').trim();
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
        this.submitButton.textContent = busy ? 'İnceleniyor…' : 'Analizi başlat';
    }
}

class ProgressCard {
    constructor(steps) {
        this.steps = steps;
    }

    render() {
        this.items = new Map();
        const rows = this.steps.map((step) => {
            const state = h('span', { class: 'run-item__state' }, 'Bekliyor');
            const row = h('li', { class: 'run-item', dataset: { status: 'pending' } },
                h('span', null, step.label), state);
            this.items.set(step.key, { row, state });
            return row;
        });
        return h('div', { class: 'card', style: { maxWidth: '560px', width: '100%', margin: '0 auto', padding: '40px', alignItems: 'center', textAlign: 'center', gap: '16px' }, 'aria-busy': 'true' },
            h('div', { style: { fontFamily: 'var(--font-heading)', fontSize: '24px' } }, 'Evrakınız inceleniyor…'),
            h('div', { style: { fontSize: '14px', color: 'var(--color-neutral-700)' } }, 'Bu işlem genellikle 1–2 dakika sürer. Sayfadan ayrılmayın.'),
            h('ol', { class: 'run-list' }, rows));
    }

    update(job) {
        const labels = { pending: 'Bekliyor', running: 'Sürüyor…', completed: 'Tamamlandı', failed: 'Başarısız', skipped: 'Atlandı' };
        for (const step of job.steps || []) {
            const entry = this.items.get(step.key);
            if (!entry) continue;
            entry.row.dataset.status = step.status;
            entry.state.textContent = labels[step.status] || step.status;
        }
    }
}

export class AnalyzeView {
    title = 'Evrak analizi';

    constructor({ api, vocab, toaster, navigate }) {
        this.api = api;
        this.vocab = vocab;
        this.toaster = toaster;
        this.navigate = navigate;
        this.poller = new JobPoller(api);
        this.progress = new ProgressCard(vocab.steps);
        this.resultView = new ResultView({ api, vocab, toaster, onNewAnalysis: () => this.reset() });
        this.input = new InputCard({
            vocab,
            onSubmit: (input) => this.run(input),
            onSample: () => { this.input.loadSample(); this.input.submit(); },
        });
        this.currentHistoryId = null;

        this.stepper = h('div', { class: 'steps' });
        this.stageRoot = h('div', { 'aria-live': 'polite' });
        this.element = h('section', { style: { display: 'flex', flexDirection: 'column', gap: '30px' } },
            h('div', { class: 'page-head' },
                h('h1', null, 'Evrak analizi'),
                h('p', null, 'Evrakınızı yükleyin veya metnini yapıştırın. Gerisini sistem yapar; son kararı her zaman siz verirsiniz.')),
            this.stepper,
            this.stageRoot);
        this.showIdle();
    }

    setStep(activeIndex) {
        const defs = [
            ['1', 'Yükleyin', 'Evrakı ekleyin'],
            ['2', 'İnceleyin', 'Sistem analiz eder'],
            ['3', 'Onaylayın', 'Taslağı kontrol edin'],
        ];
        replace(this.stepper, ...defs.map(([n, title, desc], i) => h('div', { class: `step${i <= activeIndex ? ' is-active' : ''}` },
            h('span', { class: 'step__no' }, n),
            h('span', { class: 'step__text' }, h('span', { class: 'step__title' }, title), h('span', { class: 'step__desc' }, desc)))));
    }

    async show({ id } = {}) {
        this.input.syncFromSession();
        if (id && id !== this.currentHistoryId && !this.running) await this.openRecord(id);
    }

    showIdle() {
        this.currentHistoryId = null;
        this.setStep(0);
        replace(this.stageRoot, this.input.element);
    }

    reset() {
        this.navigate('#/analiz');
        this.showIdle();
    }

    async run(input) {
        this.lastInput = input;
        this.running = true;
        this.input.setBusy(true);
        this.setStep(1);
        replace(this.stageRoot, this.progress.render());
        try {
            const { job_id: jobId } = input.kind === 'file'
                ? await this.api.startFileJob(input.file)
                : await this.api.startTextJob(input.text, input.title);
            const job = await this.poller.wait(jobId, (update) => this.progress.update(update));
            if (job.status === 'failed') throw new ApiError(job.error?.detail || 'Analiz tamamlanamadı.', { code: job.error?.code });

            const result = job.result;
            this.showResult(result, result.history_id, result.review);
            this.toaster.success(result.status === 'partial' ? 'Analiz kısmen tamamlandı; uyarıları inceleyin.' : `Analiz tamamlandı: ${input.label}`);
            if (this.element.isConnected) this.navigate(`#/analiz/${result.history_id}`);
        } catch (error) {
            this.showError(error);
        } finally {
            this.running = false;
            this.input.setBusy(false);
        }
    }

    async openRecord(id) {
        this.setStep(1);
        replace(this.stageRoot, h('div', { class: 'card', style: { maxWidth: '560px', margin: '0 auto', padding: '40px', textAlign: 'center' } }, 'Evrak yükleniyor…'));
        try {
            const record = await this.api.historyRecord(id);
            this.showResult(record.result || record, record.id, record.review);
        } catch (error) {
            this.currentHistoryId = null;
            this.showError(error);
        }
    }

    showResult(result, historyId, review) {
        this.currentHistoryId = historyId;
        this.setStep(2);
        replace(this.stageRoot, this.resultView.render(result, { historyId, review }));
    }

    showError(error) {
        this.setStep(0);
        const hint = {
            llm_unavailable: 'Yapay zekâ servisine ulaşılamadı veya kota doldu. Birkaç dakika sonra tekrar deneyin.',
            llm_auth_error: 'Sunucudaki LLM API anahtarı geçersiz. Sistem yöneticinize başvurun.',
            text_extraction_failed: 'Dosya taranmış bir görüntüyse daha net bir kopya deneyin veya metni yapıştırın.',
            network: 'Sunucu bağlantısı kesildi. Sunucunun çalıştığından emin olun.',
            pipeline_timeout: 'Analiz süresi aşıldı. Daha kısa bir metin veya daha küçük bir dosya deneyin.',
            circuit_breaker_open: 'Yapay zekâ servisi art arda hatalar nedeniyle geçici olarak devre dışı.',
        }[error.code];
        replace(this.stageRoot, h('div', { class: 'card', style: { maxWidth: '640px', margin: '0 auto', padding: '26px', gap: '14px' } },
            h('div', { class: 'alert alert--danger', role: 'alert' }, icon('circleX'),
                h('div', null, h('strong', null, 'Analiz tamamlanamadı'), error.message || 'Beklenmeyen bir hata oluştu.')),
            hint ? h('p', { class: 'muted', style: { margin: 0 } }, hint) : null,
            h('div', { style: { display: 'flex', gap: '10px', flexWrap: 'wrap' } },
                this.lastInput ? h('button', { type: 'button', class: 'btn btn-primary', onClick: () => this.run(this.lastInput) }, 'Tekrar dene') : null,
                h('button', { type: 'button', class: 'btn btn-secondary', onClick: () => this.showIdle() }, 'Geri dön'))));
    }
}
