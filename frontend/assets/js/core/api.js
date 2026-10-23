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

    history({ q = '', documentType = '', draftStatus = '', sort = '', limit = 50, offset = 0, dateFrom = '', dateTo = '', favorite } = {}) {
        const params = new URLSearchParams({ limit, offset });
        if (q) params.set('q', q);
        if (documentType) params.set('document_type', documentType);
        if (draftStatus) params.set('draft_status', draftStatus);
        if (sort) params.set('sort', sort);
        if (dateFrom) params.set('date_from', dateFrom);
        if (dateTo) params.set('date_to', dateTo);
        if (favorite !== undefined && favorite !== null) params.set('favorite', favorite);
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

    bulkDelete(ids) {
        return this.request('/history/bulk-delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ids }),
        });
    }

    healthDetailed() {
        return this.request('/health/detailed');
    }

    updateTags(recordId, tags) {
        return this.request(`/history/${encodeURIComponent(recordId)}/tags`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ tags }),
        });
    }

    toggleFavorite(recordId, favorite) {
        return this.request(`/history/${encodeURIComponent(recordId)}/favorite`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ favorite }),
        });
    }

    updateNotes(recordId, notes) {
        return this.request(`/history/${encodeURIComponent(recordId)}/notes`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ notes }),
        });
    }

    trends(days = 30) {
        return this.request(`/history/trends?days=${days}`);
    }

    duplicateRecord(recordId) {
        return this.request(`/history/${encodeURIComponent(recordId)}/duplicate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({}),
        });
    }

    validateText(text) { return this.request('/validate-text', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text }) }); }
    historyNotes(recordId) { return this.request('/history/' + encodeURIComponent(recordId)); }

    async compareTwoRecords(id1, id2) {
        return this.request('/history/compare/' + id1 + '/' + id2);
    }

    async piiAnalyze(text) {
        return this.request('/pii/analyze', { method: 'POST', json: { text } });
    }

    async systemSummary() {
        return this.request('/stats/summary');
    }

    async openApiSummary() {
        return this.request('/openapi-summary');
    }

    async recentAnalyses(count = 5) {
        return this.request('/history/recent?count=' + count);
    }

    async searchHistory(params) {
        const qs = new URLSearchParams(params).toString();
        return this.request('/history/search?' + qs);
    }

    async wordCount(text) {
        return this.request('/text/word-count', { method: 'POST', json: { text } });
    }

    async extractDates(text) {
        return this.request('/text/extract-dates', { method: 'POST', json: { text } });
    }

    async detectLanguage(text) {
        return this.request('/text/language-detect', { method: 'POST', json: { text } });
    }

    async textStatistics(text) {
        return this.request('/text/summarize-stats', { method: 'POST', json: { text } });
    }

    async statusDistribution() {
        return this.request('/history/status-distribution');
    }

    async dailyStatistics(days = 7) {
        return this.request(`/history/statistics/daily?days=${days}`);
    }

    async searchContent(keyword, limit = 20) {
        return this.request(`/history/search-content?keyword=${encodeURIComponent(keyword)}&limit=${limit}`);
    }

    async relatedRecords(recordId, limit = 5) {
        return this.request(`/history/${encodeURIComponent(recordId)}/related?limit=${limit}`);
    }

    async startupChecks() {
        return this.request('/startup-checks');
    }

    async environmentInfo() {
        return this.request('/environment');
    }

    async auditLogs(action = '') {
        const params = action ? '?action=' + action : '';
        return this.request('/audit/logs' + params);
    }

    async auditStats() {
        return this.request('/audit/stats');
    }

    async storageHealth() {
        return this.request('/health/storage');
    }

    async rateLimitStatus() {
        return this.request('/rate-limit-status');
    }

    async securityHeaders() {
        return this.request('/security-headers');
    }

    async comprehensiveHealth() { return this.request('/health/comprehensive'); }
    async systemCapabilities() { return this.request('/system/capabilities'); }
    async exportJson() { return this.request('/history/export-json'); }
    async dateRangeRecords(start, end) { const params = []; if (start) params.push('start=' + start); if (end) params.push('end=' + end); return this.request('/history/date-range' + (params.length ? '?' + params.join('&') : '')); }
    async endpointMetrics() { return this.request('/metrics/endpoints'); }
}
