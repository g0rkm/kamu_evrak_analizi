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
    503: 'Servis şu anda kullanılamıyor.',
    504: 'İşlem zaman aşımına uğradı. Daha kısa bir metin deneyin.',
};

/** Arka uç REST API'si için tek giriş noktası. */
export class ApiClient {
    constructor(baseUrl = '/api') {
        this.baseUrl = baseUrl;
    }

    async requestWithRetry(path, options = {}, { retries = 2, retryDelay = 1000 } = {}) {
        for (let attempt = 0; attempt <= retries; attempt++) {
            try {
                return await this.request(path, options);
            } catch (error) {
                const isRetryable = error.code === 'network' || error.status === 502 || error.status === 503;
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
            throw new ApiError('Sunucuya ulaşılamadı. Bağlantınızı kontrol edip tekrar deneyin.', { code: 'network' });
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

    history({ q = '', documentType = '', limit = 50, offset = 0 } = {}) {
        const params = new URLSearchParams({ limit, offset });
        if (q) params.set('q', q);
        if (documentType) params.set('document_type', documentType);
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
}
