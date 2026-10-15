document.addEventListener('DOMContentLoaded', () => {
    // DOM Elementleri
    const themeToggle = document.getElementById('themeToggle');
    const tabFileBtn = document.getElementById('tabFileBtn');
    const tabTextBtn = document.getElementById('tabTextBtn');
    const filePanel = document.getElementById('filePanel');
    const textPanel = document.getElementById('textPanel');
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    const fileInfo = document.getElementById('fileInfo');
    const fileName = document.getElementById('fileName');
    const removeFileBtn = document.getElementById('removeFileBtn');
    const textInput = document.getElementById('textInput');
    const analyzeBtn = document.getElementById('analyzeBtn');
    
    const emptyState = document.getElementById('emptyState');
    const loadingState = document.getElementById('loadingState');
    const loadingStatusText = document.getElementById('loadingStatusText');
    const copyDraftBtn = document.getElementById('copyDraftBtn');

    let selectedFile = null;
    let activeInputType = 'file'; // 'file' veya 'text'
    let currentPipelineResult = null;

    // Tema Yönetimi
    const initTheme = () => {
        if (localStorage.theme === 'dark' || (!('theme' in localStorage) && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
            document.documentElement.classList.add('dark');
        } else {
            document.documentElement.classList.remove('dark');
        }
    };
    initTheme();

    themeToggle.addEventListener('click', () => {
        if (document.documentElement.classList.contains('dark')) {
            document.documentElement.classList.remove('dark');
            localStorage.theme = 'light';
        } else {
            document.documentElement.classList.add('dark');
            localStorage.theme = 'dark';
        }
    });

    // Girdi Sekmesi Değişimi (Dosya / Metin)
    tabFileBtn.addEventListener('click', () => {
        activeInputType = 'file';
        tabFileBtn.className = "flex-1 py-2 rounded-md bg-white dark:bg-slate-600 shadow-sm transition text-center font-medium";
        tabTextBtn.className = "flex-1 py-2 rounded-md text-slate-500 dark:text-slate-400 transition text-center font-medium";
        filePanel.classList.remove('hidden');
        textPanel.classList.add('hidden');
    });

    tabTextBtn.addEventListener('click', () => {
        activeInputType = 'text';
        tabTextBtn.className = "flex-1 py-2 rounded-md bg-white dark:bg-slate-600 shadow-sm transition text-center font-medium";
        tabFileBtn.className = "flex-1 py-2 rounded-md text-slate-500 dark:text-slate-400 transition text-center font-medium";
        textPanel.classList.remove('hidden');
        filePanel.classList.add('hidden');
    });

    // Drag & Drop İşlemleri
    dropZone.addEventListener('click', () => fileInput.click());

    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            dropZone.classList.add('dragover');
        }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            dropZone.classList.remove('dragover');
        }, false);
    });

    dropZone.addEventListener('drop', (e) => {
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFileSelection(files[0]);
        }
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFileSelection(e.target.files[0]);
        }
    });

    const handleFileSelection = (file) => {
        selectedFile = file;
        fileName.textContent = file.name;
        dropZone.classList.add('hidden');
        fileInfo.classList.remove('hidden');
    };

    removeFileBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        selectedFile = null;
        fileInput.value = '';
        fileInfo.classList.add('hidden');
        dropZone.classList.remove('hidden');
    });

    // Tab Sistemi Yönetimi (Sağ Panel)
    const resultTabs = document.querySelectorAll('.result-tab');
    resultTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const tabName = tab.getAttribute('data-tab');
            
            resultTabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');

            document.querySelectorAll('.tab-content').forEach(content => {
                content.classList.add('hidden');
            });

            const targetContent = document.getElementById(`content-${tabName}`);
            if (targetContent) {
                targetContent.classList.remove('hidden');
            }
        });
    });

    // Analiz Et Butonu & API İstekleri
    analyzeBtn.addEventListener('click', async () => {
        if (activeInputType === 'file' && !selectedFile) {
            alert('Lütfen analiz için bir dosya seçin.');
            return;
        }
        if (activeInputType === 'text' && !textInput.value.trim()) {
            alert('Lütfen analiz için bir metin girin.');
            return;
        }

        setLoading(true);

        try {
            let response;
            // 120 saniye timeout için AbortController
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 120000);

            if (activeInputType === 'file') {
                const formData = new FormData();
                formData.append('file', selectedFile);

                response = await fetch('/api/analyze', {
                    method: 'POST',
                    body: formData,
                    signal: controller.signal
                });
            } else {
                response = await fetch('/api/analyze-text', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ text: textInput.value.trim() }),
                    signal: controller.signal
                });
            }

            clearTimeout(timeoutId);

            if (!response.ok) {
                throw new Error(`Sunucu hatası: ${response.statusText}`);
            }

            const data = await response.json();
            currentPipelineResult = data;
            renderResults(data);

        } catch (error) {
            console.error('Analiz hatası:', error);
            if (error.name === 'AbortError') {
                alert('İşlem zaman aşımına uğradı (120 saniye). Sunucu yanıt vermedi.');
            } else {
                alert('Analiz sırasında bir hata oluştu: ' + error.message);
            }
        } finally {
            setLoading(false);
        }
    });

    const setLoading = (isLoading) => {
        if (isLoading) {
            loadingState.classList.remove('hidden');
            // Simüle edilmiş dinamik aşama metinleri
            setTimeout(() => { loadingStatusText.textContent = "OCR ve metin çıkarma işlemleri yürütülüyor..."; }, 3000);
            setTimeout(() => { loadingStatusText.textContent = "Yapay zeka evrakı sınıflandırıyor ve varlıkları çıkarıyor..."; }, 8000);
            setTimeout(() => { loadingStatusText.textContent = "Mevzuat eşleştirmeleri ve taslak hazırlanıyor..."; }, 15000);
        } else {
            loadingState.classList.add('hidden');
        }
    };

    // Sonuçları Render Etme Fonksiyonları
    const renderResults = (data) => {
        emptyState.classList.add('hidden');
        
        // İlk taba otomatik odaklan
        document.querySelector('.result-tab[data-tab="classification"]').click();

        renderClassification(data.analysis);
        renderEntities(data.analysis);
        renderLegislation(data.analysis);
        renderDraft(data.draft);
        renderRouting(data.routing);
        renderLogs(data.agent_logs);
    };

    const renderClassification = (analysis) => {
        const cls = analysis.classification || {};
        document.getElementById('docTypeBadge').textContent = cls.document_type || 'Belirtilmemiş';
        document.getElementById('docSubType').textContent = cls.sub_type ? `(${cls.sub_type})` : '';
        
        const confidence = Math.round((cls.confidence || 0) * 100);
        document.getElementById('confidenceBar').style.width = `${confidence}%`;
        document.getElementById('confidenceText').textContent = `${confidence}%`;
        
        document.getElementById('classificationReasoning').textContent = cls.reasoning || 'Gerekçe bulunamadı.';
        document.getElementById('summaryText').textContent = analysis.summary || 'Özet bulunamadı.';
    };

    const renderEntities = (analysis) => {
        // Varlıklar Tablosu
        const tbody = document.getElementById('entitiesTableBody');
        tbody.innerHTML = '';
        const entities = analysis.entities || [];
        if (entities.length === 0) {
            tbody.innerHTML = `<tr><td colspan="3" class="p-3 text-center text-slate-400">Varlık bulunamadı.</td></tr>`;
        } else {
            entities.forEach(ent => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td class="p-3 font-medium">${ent.entity_type || '-'}</td>
                    <td class="p-3 text-slate-600 dark:text-slate-300">${ent.value || '-'}</td>
                    <td class="p-3 text-slate-400 text-xs">${ent.position || '-'}</td>
                `;
                tbody.appendChild(tr);
            });
        }

        // Eksik Alanlar
        const missingContainer = document.getElementById('missingFieldsContainer');
        missingContainer.innerHTML = '';
        const missingFields = analysis.missing_fields || [];
        if (missingFields.length === 0) {
            missingContainer.innerHTML = `<p class="text-xs text-slate-400">Eksik alan tespit edilmedi.</p>`;
        } else {
            missingFields.forEach(mf => {
                const div = document.createElement('div');
                div.className = `p-3 rounded-lg border text-xs flex items-start gap-2 ${mf.is_critical ? 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800 text-red-700 dark:text-red-300' : 'bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-800 text-amber-700 dark:text-amber-300'}`;
                div.innerHTML = `
                    <i class="fa-solid fa-circle-exclamation mt-0.5"></i>
                    <div>
                        <span class="font-bold">${mf.field_name}:</span> ${mf.description}
                    </div>
                `;
                missingContainer.appendChild(div);
            });
        }

        // Anahtar Kelimeler
        const kwContainer = document.getElementById('keywordsContainer');
        kwContainer.innerHTML = '';
        const keywords = analysis.keywords || [];
        if (keywords.length === 0) {
            kwContainer.innerHTML = `<span class="text-xs text-slate-400">Anahtar kelime yok.</span>`;
        } else {
            keywords.forEach(kw => {
                const span = document.createElement('span');
                span.className = "px-2.5 py-1 rounded-md text-xs font-medium bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300";
                span.textContent = kw;
                kwContainer.appendChild(span);
            });
        }
    };

    const renderLegislation = (analysis) => {
        const container = document.getElementById('legislationContainer');
        container.innerHTML = '';
        const matches = analysis.legislation_matches || [];
        if (matches.length === 0) {
            container.innerHTML = `<p class="text-sm text-slate-400 text-center py-6">Eşleşen mevzuat bulunamadı.</p>`;
            return;
        }

        matches.forEach(match => {
            const score = Math.round((match.relevance_score || 0) * 100);
            const card = document.createElement('div');
            card.className = "p-4 rounded-xl bg-slate-50 dark:bg-slate-700/30 border border-slate-200 dark:border-slate-700 space-y-2";
            card.innerHTML = `
                <div class="flex items-center justify-between">
                    <h4 class="font-bold text-sm text-blue-600 dark:text-blue-400">${match.legislation_name} <span class="text-xs text-slate-500 font-normal">(${match.article || ''})</span></h4>
                    <span class="px-2 py-0.5 rounded text-xs font-bold bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300">İlişki: %${score}</span>
                </div>
                <p class="text-sm text-slate-600 dark:text-slate-300">${match.summary || ''}</p>
            `;
            container.appendChild(card);
        });
    };

    const renderDraft = (draft) => {
        if (!draft) return;
        document.getElementById('draftTypeBadge').textContent = draft.draft_type || 'Taslak';
        document.getElementById('draftSubject').textContent = draft.subject || 'Konu belirtilmemiş';
        document.getElementById('draftGreeting').textContent = draft.formal_greeting || '';
        document.getElementById('draftBody').textContent = draft.body || '';
        document.getElementById('draftClosing').textContent = draft.closing || '';
        
        const toneEl = document.getElementById('draftToneCheck');
        if (draft.tone_check) {
            toneEl.textContent = draft.tone_check;
            document.getElementById('draftToneCheckContainer').classList.remove('hidden');
        } else {
            document.getElementById('draftToneCheckContainer').classList.add('hidden');
        }
    };

    copyDraftBtn.addEventListener('click', () => {
        if (!currentPipelineResult || !currentPipelineResult.draft) return;
        const d = currentPipelineResult.draft;
        const fullText = `${d.formal_greeting || ''}\n\n${d.body || ''}\n\n${d.closing || ''}`;
        navigator.clipboard.writeText(fullText).then(() => {
            const originalText = copyDraftBtn.innerHTML;
            copyDraftBtn.innerHTML = `<i class="fa-solid fa-check text-green-500"></i> Kopyalandı`;
            setTimeout(() => { copyDraftBtn.innerHTML = originalText; }, 2000);
        });
    });

    const renderRouting = (routing) => {
        if (!routing) return;
        document.getElementById('targetUnit').textContent = routing.target_unit || 'Belirtilmemiş';
        document.getElementById('routingReasoning').textContent = routing.reasoning || '';
        
        const priorityBadge = document.getElementById('priorityBadge');
        const priority = (routing.priority || 'normal').toLowerCase();
        priorityBadge.textContent = priority;
        priorityBadge.className = "px-3 py-1 rounded-full text-xs font-bold uppercase ";
        if (priority === 'acil' || priority === 'high') {
            priorityBadge.classList.add('bg-red-100', 'text-red-700', 'dark:bg-red-900/50', 'dark:text-red-300');
        } else {
            priorityBadge.classList.add('bg-blue-100', 'text-blue-700', 'dark:bg-blue-900/50', 'dark:text-blue-300');
        }

        // Alternatif Birimler
        const altContainer = document.getElementById('altUnitsContainer');
        altContainer.innerHTML = '';
        const alts = routing.alternative_units || [];
        if (alts.length === 0) {
            altContainer.innerHTML = `<span class="text-xs text-slate-400">Alternatif birim yok.</span>`;
        } else {
            alts.forEach(unit => {
                const span = document.createElement('span');
                span.className = "px-2.5 py-1 rounded-md text-xs font-medium bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300";
                span.textContent = unit;
                altContainer.appendChild(span);
            });
        }

        // Eylemler
        const actionContainer = document.getElementById('requiresActionContainer');
        actionContainer.innerHTML = '';
        const actions = routing.requires_action || [];
        if (actions.length === 0) {
            actionContainer.innerHTML = `<li class="text-xs text-slate-400 list-none">Belirtilen eylem yok.</li>`;
        } else {
            actions.forEach(act => {
                const li = document.createElement('li');
                li.textContent = act;
                actionContainer.appendChild(li);
            });
        }
    };

    const renderLogs = (logs) => {
        const logsContainer = document.getElementById('logsContainer');
        logsContainer.innerHTML = '';
        if (!logs || logs.length === 0) {
            logsContainer.innerHTML = `<div class="text-slate-500">Log kaydı bulunamadı.</div>`;
            return;
        }
        logs.forEach(log => {
            const div = document.createElement('div');
            div.className = "py-0.5 border-b border-slate-800/50 last:border-none";
            div.textContent = log;
            logsContainer.appendChild(div);
        });
    };
});
