import re
from app.agents.base_agent import BaseAgent
from app.models.analysis import AnalysisResult, ClassificationResult
from app.models.draft import DraftResponse, RoutingDecision, ValidationEntry

# Kural 1: Anahtar kelime -> evrak türü eşleştirme tablosu
KEYWORD_CLASSIFICATION_RULES = {
    "dilekce": ["dilekçe", "dilekcem", "talebim", "başvurum", "rica ederim", "müracaat"],
    "resmi_yazi": ["t.c.", "sayı:", "konu:", "ilgi:", "arz ederim", "bilgilerinize"],
    "talep_yazisi": ["talep ed", "temin edilmesi", "tahsis", "ödenek", "bütçe"],
    "bilgilendirme": ["bilginize", "bilgilerinize rica", "duyurulur", "bilgi edinilmesi"],
    "gorus_sorma": ["görüşünüz", "görüş bildir", "değerlendirmeniz", "mütalaa"],
    "sikayet": ["şikayet", "şikâyet", "mağdur", "haksızlık", "itiraz ediyorum"],
    "kurum_ici": ["hizmet içi", "personelimiz", "birimimiz", "müdürlüğümüz"],
    "genelge": ["genelge", "duyuru", "tüm birimlere", "tüm personele"],
    "rapor": ["rapor", "değerlendirme raporu", "faaliyet raporu", "inceleme sonucu"],
    "tutanak": ["tutanak", "toplantı", "katılımcılar", "gündem", "karar altına"],
    "yonetmelik": ["yönetmelik", "düzenleyici", "madde ", "hüküm", "yürürlük", "resmi gazete"],
    "teblig": ["tebliğ", "tebliği", "usul ve esaslar"],
    "kanun": ["kanun", "kanunu", "madde ", "fıkra", "bent", "yasalaş"],
    "karar": ["karar", "kararı", "kararname", "cumhurbaşkanı kararı", "kurul kararı", "atanması"],
    "kararname": ["cumhurbaşkanlığı kararnamesi", "kanun hükmünde kararname", "khk", "kararname"],
    "ilan": ["ilan", "ilân", "duyuru", "başvuru tarihi", "son başvuru"],
    "yonerge": ["yönerge", "usul ve esaslar", "çalışma esasları"],
    "sozlesme": ["sözleşme", "protokol", "mutabakat", "taraflar", "imza altına"]
}

# Kural 2: Evrak türü -> uygun taslak türü eşleştirmesi
VALID_DRAFT_TYPES = {
    "dilekce": ["cevap_yazisi", "bilgilendirme"],
    "resmi_yazi": ["cevap_yazisi", "ust_yazi", "bilgilendirme"],
    "talep_yazisi": ["cevap_yazisi", "ust_yazi"],
    "bilgilendirme": ["bilgilendirme", "ic_yazisma"],
    "gorus_sorma": ["cevap_yazisi", "ust_yazi"],
    "sikayet": ["cevap_yazisi", "bilgilendirme"],
    "kurum_ici": ["ic_yazisma", "bilgilendirme"],
    "genelge": ["bilgilendirme", "ic_yazisma"],
    "rapor": ["ust_yazi", "bilgilendirme"],
    "tutanak": ["ust_yazi", "bilgilendirme", "ic_yazisma"],
    "yonetmelik": ["bilgilendirme", "ust_yazi"],
    "teblig": ["bilgilendirme", "ust_yazi"],
    "kanun": ["bilgilendirme", "ust_yazi"],
    "karar": ["bilgilendirme", "ust_yazi", "cevap_yazisi"],
    "kararname": ["bilgilendirme", "ust_yazi"],
    "ilan": ["bilgilendirme"],
    "yonerge": ["bilgilendirme", "ic_yazisma"],
    "sozlesme": ["ust_yazi", "cevap_yazisi"]
}

# Kural 3: Anahtar kelime -> birim yönlendirme tablosu
KEYWORD_ROUTING_RULES = {
    "Hukuk Müşavirliği": ["dava", "mahkeme", "hukuk", "sözleşme", "mevzuat", "kanun", "yönetmelik", "itiraz", "idari yargı"],
    "İnsan Kaynakları Daire Başkanlığı": ["personel", "atama", "izin", "özlük", "sicil", "disiplin", "memur", "kadro"],
    "Strateji Geliştirme Daire Başkanlığı": ["bütçe", "ödenek", "planlama", "performans", "istatistik", "mali"],
    "Bilgi Teknolojileri Daire Başkanlığı": ["yazılım", "bilişim", "siber", "sunucu", "ağ", "bilgi sistemi", "e-devlet"],
    "İdari ve Mali İşler Daire Başkanlığı": ["satın alma", "ihale", "lojistik", "taşınır", "demirbaş", "kira", "bakım"],
    "Basın ve Halkla İlişkiler Müdürlüğü": ["basın", "medya", "cimer", "halkla ilişkiler", "kamuoyu", "vatandaş başvuru"],
    "Teftiş Kurulu Başkanlığı": ["denetim", "soruşturma", "teftiş", "müfettiş", "inceleme", "usulsüzlük"]
}

# Kural 4: Evrak türü -> öncelik seviyeleri
PRIORITY_RULES = {
    "sikayet": "yuksek",
    "gorus_sorma": "normal",
    "genelge": "normal",
    "tutanak": "normal",
    "dilekce": "normal",
    "talep_yazisi": "normal",
    "resmi_yazi": "normal",
    "bilgilendirme": "dusuk",
    "kurum_ici": "dusuk",
    "rapor": "normal",
    "yonetmelik": "normal",
    "teblig": "normal",
    "kanun": "yuksek",
    "karar": "yuksek",
    "kararname": "yuksek",
    "ilan": "dusuk",
    "yonerge": "normal",
    "sozlesme": "normal"
}

# Acil anahtar kelimeler
URGENT_KEYWORDS = ["acil", "ivedi", "derhal", "süre dolmak üzere", "son gün", "zamanaşımı", "mahkeme süresi"]


class ReasoningAgent(BaseAgent):
    """Kural tabanlı muhakeme ajanı. LLM çağırmaz, deterministik çalışır."""

    def __init__(self):
        super().__init__(name="ReasoningAgent", llm_service=None)

    async def execute(self, text: str, analysis: AnalysisResult,
                      draft: DraftResponse = None,
                      routing: RoutingDecision = None) -> dict:
        """Tüm agent çıktılarını kural tabanlı mantıkla doğrula ve düzelt.
        
        Returns:
            dict with keys: analysis, draft, routing, validation, confidence_score
        """
        self.log("Muhakeme başlatılıyor...")
        validation = []
        text_lower = text.lower()

        # ── KURAL 1: Sınıflandırma doğrulaması ──
        keyword_type = self._detect_type_by_keywords(text_lower)
        llm_type = analysis.classification.document_type

        if keyword_type and keyword_type != llm_type:
            keyword_count = self._count_keyword_matches(text_lower, keyword_type)
            llm_keyword_count = self._count_keyword_matches(text_lower, llm_type)

            if keyword_count > llm_keyword_count:
                validation.append(ValidationEntry(
                    field="classification.document_type",
                    original_value=llm_type,
                    corrected_value=keyword_type,
                    rule="keyword_classification",
                    severity="correction"
                ))
                analysis.classification = ClassificationResult(
                    document_type=keyword_type,
                    confidence=min(analysis.classification.confidence, 0.7),
                    sub_type=analysis.classification.sub_type,
                    reasoning=f"Muhakeme düzeltmesi: Anahtar kelime analizi '{keyword_type}' türünü destekliyor (orijinal: {llm_type})"
                )
                self.log(f"Sınıflandırma düzeltildi: {llm_type} -> {keyword_type}")
            else:
                validation.append(ValidationEntry(
                    field="classification.document_type",
                    original_value=llm_type,
                    rule="keyword_classification",
                    severity="info"
                ))

        # ── KURAL 2: Taslak türü tutarlılığı ──
        if draft:
            doc_type = analysis.classification.document_type
            valid_drafts = VALID_DRAFT_TYPES.get(doc_type, [])
            if valid_drafts and draft.draft_type not in valid_drafts:
                corrected_draft_type = valid_drafts[0]
                validation.append(ValidationEntry(
                    field="draft.draft_type",
                    original_value=draft.draft_type,
                    corrected_value=corrected_draft_type,
                    rule="draft_type_consistency",
                    severity="correction"
                ))
                draft = DraftResponse(
                    draft_type=corrected_draft_type,
                    subject=draft.subject,
                    body=draft.body,
                    formal_greeting=draft.formal_greeting,
                    closing=draft.closing,
                    attachments_note=draft.attachments_note,
                    tone_check=f"Taslak türü '{draft.draft_type}' -> '{corrected_draft_type}' olarak düzeltildi (evrak türü: {doc_type})"
                )
                self.log(f"Taslak türü düzeltildi: {draft.draft_type} -> {corrected_draft_type}")

        # ── KURAL 3: Yönlendirme doğrulaması ──
        if routing:
            keyword_unit = self._detect_unit_by_keywords(text_lower)
            if keyword_unit and keyword_unit != routing.target_unit:
                keyword_unit_count = self._count_unit_keyword_matches(text_lower, keyword_unit)
                current_unit_count = self._count_unit_keyword_matches(text_lower, routing.target_unit)

                if keyword_unit_count > current_unit_count:
                    old_unit = routing.target_unit
                    validation.append(ValidationEntry(
                        field="routing.target_unit",
                        original_value=old_unit,
                        corrected_value=keyword_unit,
                        rule="keyword_routing",
                        severity="correction"
                    ))
                    if old_unit not in routing.alternative_units:
                        routing.alternative_units.insert(0, old_unit)
                    routing = RoutingDecision(
                        target_unit=keyword_unit,
                        reasoning=f"Muhakeme düzeltmesi: Anahtar kelime analizi '{keyword_unit}' birimini destekliyor (orijinal: {old_unit})",
                        priority=routing.priority,
                        alternative_units=routing.alternative_units,
                        requires_action=routing.requires_action
                    )
                    self.log(f"Yönlendirme düzeltildi: {old_unit} -> {keyword_unit}")

        # ── KURAL 4: Öncelik doğrulaması ──
        if routing:
            has_urgent = any(kw in text_lower for kw in URGENT_KEYWORDS)
            expected_priority = "acil" if has_urgent else PRIORITY_RULES.get(analysis.classification.document_type, "normal")

            if routing.priority != expected_priority:
                validation.append(ValidationEntry(
                    field="routing.priority",
                    original_value=routing.priority,
                    corrected_value=expected_priority,
                    rule="priority_rules",
                    severity="correction"
                ))
                routing = RoutingDecision(
                    target_unit=routing.target_unit,
                    reasoning=routing.reasoning,
                    priority=expected_priority,
                    alternative_units=routing.alternative_units,
                    requires_action=routing.requires_action
                )
                self.log(f"Öncelik düzeltildi: {routing.priority} -> {expected_priority}")

        # ── KURAL 5: Eksik alan kontrolü (kural tabanlı) ──
        required_patterns = {
            "tarih": [r'\d{2}[./]\d{2}[./]\d{4}', r'\d{4}[./]\d{2}[./]\d{2}'],
            "sayi": [r'sayı\s*:\s*\S+', r'say[ıi]\s*:\s*\S+'],
            "konu": [r'konu\s*:\s*.+'],
            "imza": [r'arz ederim', r'rica ederim', r'saygılarımla']
        }
        for field_name, patterns in required_patterns.items():
            found = any(re.search(p, text_lower) for p in patterns)
            already_missing = any(mf.field_name == field_name for mf in analysis.missing_fields)
            if not found and not already_missing:
                from app.models.analysis import MissingField
                analysis.missing_fields.append(MissingField(
                    field_name=field_name,
                    description=f"Kural tabanlı kontrol: '{field_name}' alanı metinde tespit edilemedi",
                    is_critical=(field_name in ["tarih", "sayi"])
                ))
                validation.append(ValidationEntry(
                    field=f"missing_fields.{field_name}",
                    original_value="not_detected",
                    rule="pattern_missing_field",
                    severity="warning"
                ))

        # ── Güven skoru hesaplama ──
        corrections = sum(1 for v in validation if v.severity == "correction")
        warnings = sum(1 for v in validation if v.severity == "warning")
        base_confidence = analysis.classification.confidence
        confidence_score = max(0.0, min(1.0,
            base_confidence - (corrections * 0.15) - (warnings * 0.05)
        ))

        self.log(f"Muhakeme tamamlandı: {len(validation)} bulgu, güven: {confidence_score:.2f}")

        return {
            "analysis": analysis,
            "draft": draft,
            "routing": routing,
            "validation": validation,
            "confidence_score": round(confidence_score, 2)
        }

    def _detect_type_by_keywords(self, text_lower: str) -> str | None:
        best_type = None
        best_count = 0
        for doc_type, keywords in KEYWORD_CLASSIFICATION_RULES.items():
            count = sum(1 for kw in keywords if kw in text_lower)
            if count > best_count:
                best_count = count
                best_type = doc_type
        return best_type if best_count >= 2 else None

    def _count_keyword_matches(self, text_lower: str, doc_type: str) -> int:
        keywords = KEYWORD_CLASSIFICATION_RULES.get(doc_type, [])
        return sum(1 for kw in keywords if kw in text_lower)

    def _detect_unit_by_keywords(self, text_lower: str) -> str | None:
        best_unit = None
        best_count = 0
        for unit, keywords in KEYWORD_ROUTING_RULES.items():
            count = sum(1 for kw in keywords if kw in text_lower)
            if count > best_count:
                best_count = count
                best_unit = unit
        return best_unit if best_count >= 2 else None

    def _count_unit_keyword_matches(self, text_lower: str, unit: str) -> int:
        keywords = KEYWORD_ROUTING_RULES.get(unit, [])
        return sum(1 for kw in keywords if kw in text_lower)
