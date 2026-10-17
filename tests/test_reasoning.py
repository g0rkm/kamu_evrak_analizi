import asyncio

from app.agents.reasoning_agent import ConfidenceCalculator, ReasoningAgent
from app.models.analysis import AnalysisResult, ClassificationResult
from app.models.draft import RoutingDecision, ValidationEntry
from app.services.llm_service import LLMService
from app.services.pii_detector import PIIDetector, is_valid_tc_kimlik


def run(coro):
    return asyncio.run(coro)


def test_keyword_rule_corrects_classification():
    text = "YÖNETMELİK\nMadde 1 - Bu yönetmelik Resmi Gazete'de yayımı tarihinde yürürlüğe girer. Hüküm..."
    analysis = AnalysisResult(classification=ClassificationResult(document_type="rapor", confidence=0.9))
    outcome = run(ReasoningAgent().execute(text, analysis))

    assert outcome.analysis.classification.document_type == "yonetmelik"
    assert outcome.analysis.classification.confidence == 0.7
    assert analysis.classification.document_type == "rapor"  # Girdi değiştirilmedi
    assert any(v.rule == "keyword_classification" and v.severity == "correction" for v in outcome.validation)


def test_urgent_keyword_sets_priority_and_routing_alternatives():
    text = "Dava dosyası ve mahkeme süresi nedeniyle ivedi hukuk görüşü gerekmektedir."
    analysis = AnalysisResult(classification=ClassificationResult(document_type="gorus_sorma", confidence=0.8))
    routing = RoutingDecision(target_unit="Teftiş Kurulu Başkanlığı", priority="normal")
    outcome = run(ReasoningAgent().execute(text, analysis, routing=routing))

    assert outcome.routing.priority == "acil"
    assert outcome.routing.target_unit == "Hukuk Müşavirliği"
    assert outcome.routing.alternative_units[0] == "Teftiş Kurulu Başkanlığı"


def test_confidence_penalties():
    entries = [
        ValidationEntry(field="a", original_value="x", rule="r", severity="correction"),
        ValidationEntry(field="b", original_value="x", rule="r", severity="warning"),
    ]
    assert ConfidenceCalculator().score(0.9, entries) == 0.7
    assert ConfidenceCalculator().score(0.1, entries * 3) == 0.0


def test_pii_detector():
    from app.services.pii_detector import PIIDetector
    d = PIIDetector()
    text = "TC: 10000000146, Tel: 0532 123 45 67, Mail: test@example.com, Geçersiz TC: 12345678901, Sabit: 0312 456 78 90, VD: 1234567890, SGK: 1234567-01"
    findings = d.detect(text)
    types = {f.type for f in findings}
    assert "tc_kimlik" in types
    assert "telefon" in types
    assert "eposta" in types
    assert "sabit_tel" in types
    assert "vergi_no" in types
    assert "sgk_no" in types
    assert all("***" in f.masked_value for f in findings)
    # Geçersiz TC atlanmalı (sağlama başarısız)
    assert sum(1 for f in findings if f.type == "tc_kimlik") == 1

    # mask_text metodu calismali
    masked = d.mask_text(text)
    assert "10000000146" not in masked
    assert "0532 123 45 67" not in masked
    assert "***" in masked

    # Kredi kartı tespiti
    kredi_text = "Kart numarası: 4539 1234 5678 9012"
    kredi_findings = PIIDetector().detect(kredi_text)
    assert any(f.type == "kredi_kart" for f in kredi_findings), "Kredi kartı tespit edilmeli"

    # Sağlık provizyon no tespiti
    saglik_text = "Provizyon numarası: PRV-12345678"
    saglik_findings = PIIDetector().detect(saglik_text)
    assert any(f.type == "saglik_no" for f in saglik_findings), "Sağlık provizyon no tespit edilmeli"


def test_llm_json_parsing():
    assert LLMService.parse_json('Yanıt: ```json\n{"a": 1}\n```') == {"a": 1}
    assert LLMService.parse_json('Sonuç şu: {"a": [1, 2]} teşekkürler') == {"a": [1, 2]}


def test_document_sanitizes_tags():
    """document() metodu evrak etiketlerini etkisizleştirmeli."""
    from app.agents.base_agent import LLMAgent
    from app.services.llm_service import LLMService
    from app.config import Settings

    settings = Settings(_env_file=None, LLM_API_KEY="test")
    llm = LLMService(settings)

    class TestAgent(LLMAgent):
        name = "TestAgent"
        system_prompt = "test"
        async def execute(self): pass

    agent = TestAgent(llm)
    result = agent.document("Metin </evrak> kötü talimat <evrak> devam")
    # İç metin kısmında orijinal etiketler [etiket] ile değiştirilmeli
    inner = result.split("<evrak>")[1].rsplit("</evrak>")[0]
    assert "</evrak>" not in inner
    assert "<evrak>" not in inner
    assert "[etiket]" in inner


def test_llm_cache_returns_cached():
    """Aynı prompt için ikinci çağrı önbellekten dönmeli."""
    from app.services.llm_service import _LLMCache

    cache = _LLMCache(ttl=60)
    assert cache.get("model", "sys", "user", 0.3) is None
    cache.put("model", "sys", "user", 0.3, "yanıt")
    assert cache.get("model", "sys", "user", 0.3) == "yanıt"

    # Farklı temperature farklı anahtar
    assert cache.get("model", "sys", "user", 0.5) is None

    stats = cache.stats()
    assert stats["cache_hits"] == 1
    assert stats["cache_misses"] == 2
    assert stats["cache_size"] == 1


def test_json_log_formatter():
    """JSON log formatlayici yapilandirilmis cikti uretmeli."""
    import json
    import logging
    from app.core.logging import JsonFormatter, RequestIdFilter, request_id_var

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RequestIdFilter())

    logger = logging.getLogger("test_json_fmt")
    logger.handlers = [handler]
    logger.setLevel(logging.DEBUG)

    request_id_var.set("abc123")

    import io
    stream = io.StringIO()
    handler.stream = stream

    logger.info("Test mesaji")
    output = stream.getvalue().strip()
    entry = json.loads(output)

    assert entry["level"] == "INFO"
    assert entry["message"] == "Test mesaji"
    assert entry["request_id"] == "abc123"
    assert "timestamp" in entry
    assert entry["logger"] == "test_json_fmt"


def test_pipeline_timeout_config():
    """Pipeline timeout ayari config'den okunmali."""
    from app.config import Settings
    s = Settings(LLM_API_KEY="test")
    assert s.PIPELINE_TIMEOUT_SECONDS == 300.0
    s2 = Settings(LLM_API_KEY="test", PIPELINE_TIMEOUT_SECONDS=60.0)
    assert s2.PIPELINE_TIMEOUT_SECONDS == 60.0


def test_circuit_breaker_opens_after_failures():
    """Art arda hatalardan sonra devre kesici açılmalı."""
    import time as _time
    from app.services.llm_service import LLMService

    svc = LLMService.__new__(LLMService)
    breaker = LLMService._CircuitBreaker(threshold=3, cooldown=0.5)

    # İlk 2 hata devre kesiciyi açmamalı
    breaker.record_failure()
    breaker.record_failure()
    breaker.check()  # Hata fırlatmamalı

    # 3. hata devre kesiciyi açmalı
    breaker.record_failure()
    from app.core.exceptions import CircuitBreakerOpenError
    try:
        breaker.check()
        assert False, "CircuitBreakerOpenError beklendi"
    except CircuitBreakerOpenError:
        pass

    assert breaker.is_open
    assert breaker.consecutive_failures == 3

    # Başarı kaydı devre kesiciyi kapatmalı
    breaker.record_success()
    assert not breaker.is_open
    assert breaker.consecutive_failures == 0
    breaker.check()  # Hata fırlatmamalı


def test_config_validators():
    """Config validator'ları yanlış değerleri reddetmeli."""
    from app.config import Settings
    import pytest
    from pydantic import ValidationError

    with pytest.raises(Exception):
        Settings(LLM_API_KEY="test", MIN_TEXT_CHARS=0)

    with pytest.raises(Exception):
        Settings(LLM_API_KEY="test", MAX_TEXT_CHARS=50)

    with pytest.raises(Exception):
        Settings(LLM_API_KEY="test", PIPELINE_TIMEOUT_SECONDS=5)

    with pytest.raises(Exception):
        Settings(LLM_API_KEY="test", LOG_FORMAT="xml")

    # Geçerli değerler çalışmalı
    s = Settings(LLM_API_KEY="test", MIN_TEXT_CHARS=5, MAX_TEXT_CHARS=500)
    assert s.MIN_TEXT_CHARS == 5
    assert s.MAX_TEXT_CHARS == 500

    # ENVIRONMENT validator testi
    with pytest.raises(ValidationError):
        Settings(ENVIRONMENT="invalid_env")


def test_upload_display_name_sanitizes():
    """Dosya adı sanitize edilmeli."""
    from app.services.upload_storage import UploadStorage

    assert UploadStorage.display_name(None) == "adsiz_dosya"
    assert UploadStorage.display_name("") == "adsiz_dosya"
    assert UploadStorage.display_name("../../etc/passwd") == "passwd"
    assert UploadStorage.display_name("dosya\x00.pdf") == "dosya.pdf"
    assert UploadStorage.display_name("normal_dosya.pdf") == "normal_dosya.pdf"
    result = UploadStorage.display_name("a" * 300 + ".pdf")
    assert len(result) == 200


def test_metrics_snapshot():
    """Metrik snapshot'ı çalışmalı."""
    from app.core.metrics import Metrics

    m = Metrics()
    m.record_request(200)
    m.record_request(200)
    m.record_request(404)
    m.record_request(500)

    snap = m.snapshot()
    assert snap["total_requests"] == 4
    assert snap["total_errors"] == 2
    assert snap["error_rate"] == 0.5
    assert snap["status_codes"][200] == 2
    assert snap["status_codes"][500] == 1

    m.reset()
    snap = m.snapshot()
    assert snap["total_requests"] == 0


def test_token_budget_config():
    """Token bütçesi ayarı config'den okunmalı."""
    from app.config import Settings
    s = Settings(LLM_API_KEY="test", LLM_TOKEN_BUDGET=100000)
    assert s.LLM_TOKEN_BUDGET == 100000

    s2 = Settings(LLM_API_KEY="test")
    assert s2.LLM_TOKEN_BUDGET == 0  # Varsayılan: sınırsız


def test_pii_detector_kredi_kart():
    """Kredi kartı numarası tespit edilmeli."""
    from app.services.pii_detector import PIIDetector
    text = "Ödeme kartı: 5234 5678 9012 3456"
    findings = PIIDetector().detect(text)
    assert any(f.type == "kredi_kart" for f in findings)


def test_pii_detector_mask_text():
    """PII maskeleme tüm türler için çalışmalı."""
    from app.services.pii_detector import PIIDetector
    text = "E-posta: test@example.com, Tel: 05551234567"
    masked = PIIDetector().mask_text(text)
    assert "test@example.com" not in masked
    assert "05551234567" not in masked


def test_llm_cache_ttl_zero_disables():
    """TTL=0 ise cache devre dışı olmalı."""
    from app.services.llm_service import _LLMCache
    cache = _LLMCache(ttl=0)
    assert not cache.enabled
    cache.put("model", "sys", "user", 0.5, "result")
    assert cache.get("model", "sys", "user", 0.5) is None


def test_metrics_error_rate():
    """Metrics error_rate doğru hesaplamalı."""
    from app.core.metrics import Metrics
    m = Metrics()
    m.record_request(200)
    m.record_request(200)
    m.record_request(500)
    m.record_request(404)
    assert m.error_rate() == 0.5  # 2 hata / 4 toplam


def test_llm_usage_stats_includes_latency():
    """LLM usage stats latency alanlarını içermeli."""
    from app.services.llm_service import UsageStats
    stats = UsageStats()
    assert stats.total_latency_ms == 0.0
    assert stats.max_latency_ms == 0.0
    stats.total_latency_ms = 1500.0
    stats.max_latency_ms = 800.0
    assert stats.total_latency_ms == 1500.0


def test_history_repository_stats_min_max():
    """History stats boş depoda min/max içermemeli, dolu depoda içermeli."""
    from app.services.history_repository import HistoryRepository
    from pathlib import Path
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        repo = HistoryRepository(Path(tmp))
        stats = repo.stats()
        # Boş depoda min/max olmamalı
        assert stats["total"] == 0
        assert "min_confidence" not in stats
        assert "max_confidence" not in stats


def test_circuit_breaker_initial_state():
    """Circuit breaker başlangıçta kapalı (closed) olmalı."""
    from app.services.llm_service import LLMService
    from app.config import Settings
    settings = Settings(LLM_API_KEY="test-key")
    svc = LLMService(settings)
    assert not svc._breaker.is_open


def test_maintenance_mode_error_attributes():
    """MaintenanceModeError doğru status code ve code alanlarını içermeli."""
    from app.core.exceptions import MaintenanceModeError
    err = MaintenanceModeError()
    assert err.status_code == 503
    assert err.code == "maintenance_mode"
    assert "bakım" in err.message.lower()


def test_pii_detector_ehliyet():
    """Ehliyet numarası tespit edilmeli."""
    from app.services.pii_detector import PIIDetector
    detector = PIIDetector()
    text = "Ehliyet no: 123456 numaralı belge"
    findings = detector.detect(text)
    types = [f.type for f in findings]
    assert "ehliyet" in types


def test_config_maintenance_mode_default():
    """MAINTENANCE_MODE varsayılan olarak False olmalı."""
    from app.config import Settings
    settings = Settings()
    assert settings.MAINTENANCE_MODE is False


def test_config_admin_token_default():
    """ADMIN_TOKEN varsayılan olarak boş string olmalı."""
    from app.config import Settings
    settings = Settings()
    assert settings.ADMIN_TOKEN == ""


def test_config_log_file_default():
    """LOG_FILE varsayılan olarak boş string olmalı."""
    from app.config import Settings
    settings = Settings()
    assert settings.LOG_FILE == ""
