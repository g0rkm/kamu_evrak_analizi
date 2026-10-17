export class ApiError extends Error {
    constructor(message, { status = 0, code = 'unknown' } = {}) {
        super(message);
        this.name = 'ApiError';
        this.status = status;
        this.code = code;
    }
}

const STATUS_MESSAGES = {
    400: 'İstek geçersiz.',
    404: 'Kayıt bulunamadı.',
    413: 'Dosya çok büyük.',
    415: 'Bu dosya türü desteklenmiyor.',
    422: 'Gönderilen veriler doğrulanamadı.',
    429: 'Çok fazla istek gönderildi. Lütfen biraz bekleyin.',
    500: 'Sunucuda beklenmeyen bir hata oluştu.',
    502: 'Yapay zekâ servisi isteği işleyemedi.',
    503: 'Servis şu anda kullanılamıyor. Birkaç dakika sonra tekrar deneyin.',
    504: 'İşlem zaman aşımına uğradı. Daha kısa bir metin deneyin.',
};

/** Arka uç REST API'si için tek giriş noktası. */
export class ApiClient {
    constructor(baseUrl = '/api') {
        this.baseUrl = baseUrl;
    }

    isOnline() {
        return typeof navigator.onLine === 'boolean' ? navigator.onLine : true;
    }

    requestWithTimeout(path, options = {}, timeoutMs = 30000) {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), timeoutMs);
        return this.request(path, { ...options, signal: controller.signal })
            .finally(() => clearTimeout(timer));
    }

    async requestWithRetry(path, options = {}, { retries = 2, retryDelay = 1000 } = {}) {
        for (let attempt = 0; attempt <= retries; attempt++) {
            try {
                return await this.request(path, options);
            } catch (error) {
                const isRetryable = error.code === 'network' || error.code === 'network_error' || error.status === 502 || error.status === 503;
                if (!isRetryable || attempt === retries) throw error;
                const delay = retryDelay * Math.pow(2, attempt);
                await new Promise(r => setTimeout(r, delay));
            }
        }
    }

    async request(path, { method = 'GET', json, body, signal } = {}) {
        const init = { method, signal, headers: { Accept: 'application/json' } };
        if (json !== undefined) {
            init.headers['Content-Type'] = 'application/json';
            init.body = JSON.stringify(json);
        } else if (body !== undefined) {
            init.body = body;
        }

        let response;
        try {
            response = await fetch(`${this.baseUrl}${path}`, init);
        } catch (error) {
            if (error.name === 'AbortError') throw error;
            if (error instanceof TypeError) {
                throw new ApiError('Sunucuya bağlanılamadı. İnternet bağlantınızı kontrol edin.', { code: 'network_error' });
            }
            const offlineMsg = !this.isOnline() ? 'İnternet bağlantınız yok. Çevrimiçi olduğunuzda tekrar deneyin.' : 'Sunucuya ulaşılamadı. Bağlantınızı kontrol edip tekrar deneyin.';
            throw new ApiError(offlineMsg, { code: 'network' });
        }

        const data = await response.json().catch(() => null);
        if (!response.ok) {
            const detail = typeof data?.detail === 'string' ? data.detail : null;
            throw new ApiError(detail || STATUS_MESSAGES[response.status] || `İstek başarısız (HTTP ${response.status}).`, {
                status: response.status,
                code: data?.code || 'http_error',
            });
        }
        return data;
    }

    health() { return this.request('/health'); }
    meta() { return this.request('/meta'); }

    startTextJob(text, title) {
        return this.request('/jobs/text', { method: 'POST', json: { text, title: title || null } });
    }

    startFileJob(file) {
        const form = new FormData();
        form.append('file', file);
        return this.request('/jobs/file', { method: 'POST', body: form });
    }

    job(jobId, signal) { return this.request(`/jobs/${encodeURIComponent(jobId)}`, { signal }); }

    history({ q = '', documentType = '', draftStatus = '', sort = '', limit = 50, offset = 0 } = {}) {
        const params = new URLSearchParams({ limit, offset });
        if (q) params.set('q', q);
        if (documentType) params.set('document_type', documentType);
        if (draftStatus) params.set('draft_status', draftStatus);
        if (sort) params.set('sort', sort);
        return this.request(`/history?${params}`);
    }

    historyStats() { return this.request('/history/stats'); }
    historyRecord(id) { return this.request(`/history/${encodeURIComponent(id)}`); }
    deleteRecord(id) { return this.request(`/history/${encodeURIComponent(id)}`, { method: 'DELETE' }); }

    updateReview(id, patch) {
        return this.request(`/history/${encodeURIComponent(id)}/review`, { method: 'PATCH', json: patch });
    }

    compare(text1, text2) { return this.request('/compare', { method: 'POST', json: { text1, text2 } }); }
    maskPii(text) { return this.request('/mask-pii', { method: 'POST', json: { text } }); }

    exportRecord(id) {
        return this.request(`/export/${encodeURIComponent(id)}`);
    }

    exportAllRecords() {
        return this.request('/history/export-all');
    }

    clearAllRecords() {
        return this.request('/history/clear', { method: 'DELETE' });
    }

    importRecords(records) {
        return this.request('/history/import', { method: 'POST', json: { records } });
    }

    systemInfo() {
        return this.request('/system-info');
    }

    llmStats() {
        return this.request('/stats/llm');
    }

    configExport() {
        return this.request('/config/export');
    }

    clearCache() {
        return this.request('/cache/clear', { method: 'POST', json: {} });
    }

    readinessCheck() {
        return this.request('/ready');
    }

    requestStats() {
        return this.request('/stats/requests');
    }

    exportCsv() {
        return fetch(`${this.baseUrl}/history/export-csv`).then(r => {
            if (!r.ok) throw new Error('CSV indirilemedi.');
            return r.blob();
        });
    }

    configExportData() {
        return this.request('/config/export');
    }
}
