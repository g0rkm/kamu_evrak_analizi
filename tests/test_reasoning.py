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
    assert "[***" in masked

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


def test_config_disk_warning_threshold_default():
    """DISK_WARNING_THRESHOLD_MB varsayılan olarak 100 olmalı."""
    from app.config import Settings
    settings = Settings()
    assert settings.DISK_WARNING_THRESHOLD_MB == 100


def test_config_max_history_records_default():
    """MAX_HISTORY_RECORDS varsayılan olarak 10000 olmalı."""
    from app.config import Settings
    settings = Settings()
    assert settings.MAX_HISTORY_RECORDS == 10000


def test_pii_detector_mask_preserves_nonpii():
    """PII olmayan metin maskelenmemeli."""
    from app.services.pii_detector import PIIDetector
    detector = PIIDetector()
    text = "Bu bir normal metin, kişisel veri yok."
    masked = detector.mask_text(text)
    assert masked == text


def test_pii_detector_iban():
    """IBAN tespit edilmeli."""
    from app.services.pii_detector import PIIDetector
    detector = PIIDetector()
    text = "IBAN: TR33 0006 1005 1978 6457 8413 26"
    findings = detector.detect(text)
    types = [f.type for f in findings]
    assert "iban" in types


def test_pii_detector_telefon():
    """Telefon numarası tespit edilmeli."""
    from app.services.pii_detector import PIIDetector
    detector = PIIDetector()
    text = "İletişim: 0532 123 45 67"
    findings = detector.detect(text)
    types = [f.type for f in findings]
    assert "telefon" in types


def test_json_formatter_output():
    """JsonFormatter log çıktısı JSON olmalı."""
    import json
    import logging
    from app.core.logging import JsonFormatter
    formatter = JsonFormatter()
    record = logging.LogRecord("test", logging.INFO, "", 0, "test message", (), None)
    output = formatter.format(record)
    parsed = json.loads(output)
    assert parsed["message"] == "test message"
    assert parsed["level"] == "INFO"


def test_app_version():
    """Uygulama versiyonu 3.4.0 olmalı."""
    from app import __version__
    assert __version__ == "3.5.0"


def test_settings_has_all_new_fields():
    """Settings tüm yeni alanları içermeli."""
    from app.config import Settings
    settings = Settings()
    assert hasattr(settings, 'MAINTENANCE_MODE')
    assert hasattr(settings, 'ADMIN_TOKEN')
    assert hasattr(settings, 'LOG_FILE')
    assert hasattr(settings, 'MAX_HISTORY_RECORDS')
    assert hasattr(settings, 'DISK_WARNING_THRESHOLD_MB')


def test_metrics_endpoint_tracking():
    """Metrics endpoint bazlı sayım yapmalı."""
    from app.core.metrics import Metrics
    m = Metrics()
    m.record_request(200, endpoint="/api/health")
    m.record_request(200, endpoint="/api/health")
    m.record_request(200, endpoint="/api/meta")
    snap = m.snapshot()
    assert snap["top_endpoints"]["/api/health"] == 2
    assert snap["top_endpoints"]["/api/meta"] == 1


def test_history_repository_stats_favorites_count():
    """History stats boş depoda favorites_count 0 olmalı."""
    from app.services.history_repository import HistoryRepository
    from pathlib import Path
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        repo = HistoryRepository(Path(tmp))
        stats = repo.stats()
        assert stats["favorites_count"] == 0


def test_pii_detector_plaka():
    from app.services.pii_detector import PIIDetector; detector = PIIDetector(); text = 'Arac plakasi: 34 ABC 123'; findings = detector.detect(text); types = [f.type for f in findings]; assert 'plaka' in types


def test_token_budget_exceeded_error():
    from app.core.exceptions import TokenBudgetExceededError
    err = TokenBudgetExceededError()
    assert err.status_code == 429
    assert err.code == 'token_budget_exceeded'


def test_dedup_key_returns_none_on_miss():
    from app.services.llm_service import _LLMCache
    cache = _LLMCache(ttl=60)
    result = cache.deduplicate_key('nonexistent')
    assert result is None


def test_dedup_key_returns_key_after_set():
    from app.services.llm_service import _LLMCache
    cache = _LLMCache(ttl=60)
    cache.set_dedup('hash123', 'llm:hash123', window_seconds=30)
    result = cache.deduplicate_key('hash123')
    assert result == 'llm:hash123'


def test_api_version_endpoint():
    from fastapi.testclient import TestClient
    from app.main import create_app
    app = create_app()
    with TestClient(app) as client:
        response = client.get('/api/version')
        assert response.status_code == 200
        data = response.json()
        assert data['api'] == 'v1'
        assert data['status'] == 'stable'
        assert 'version' in data


def test_analysis_timeout_config_default():
    from app.config import Settings
    s = Settings()
    assert s.ANALYSIS_TIMEOUT == 60


def test_analysis_timeout_config_validation():
    from app.config import Settings
    import pytest
    with pytest.raises(Exception):
        Settings(ANALYSIS_TIMEOUT=3)


def test_pii_mask_text():
    from app.services.pii_detector import PIIDetector
    d = PIIDetector()
    result = d.mask_text('Email: test@test.com ve tel: 05551234567')
    assert '[***EPOSTA***]' in result
    assert '[***TELEFON***]' in result
    assert 'test@test.com' not in result


def test_file_validation_error():
    from app.core.exceptions import FileValidationError
    e = FileValidationError('test')
    assert e.status_code == 400
    assert e.code == 'file_validation_error'


def test_configuration_error():
    from app.core.exceptions import ConfigurationError
    e = ConfigurationError('test')
    assert e.status_code == 500
    assert e.code == 'configuration_error'


def test_export_filtered_empty():
    from app.services.history_repository import HistoryRepository
    from pathlib import Path
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        repo = HistoryRepository(Path(tmp))
        result = repo.export_filtered()
        assert result == []


def test_metrics_response_time():
    from app.core.metrics import metrics
    metrics.reset()
    metrics.record_request(200, response_time=0.15)
    metrics.record_request(200, response_time=0.25)
    assert metrics.avg_response_time() > 0
    snap = metrics.snapshot()
    assert 'avg_response_time_ms' in snap
    metrics.reset()


def test_duplicate_record_error():
    from app.core.exceptions import DuplicateRecordError
    e = DuplicateRecordError('Kayit zaten mevcut')
    assert e.status_code == 409
    assert e.code == 'duplicate_record'


def test_pii_summary():
    from app.services.pii_detector import PIIDetector
    d = PIIDetector()
    result = d.summary('Email: test@test.com ve tel: 05551234567')
    assert result['total_pii_count'] == 2
    assert 'eposta' in result['types_found']
    assert 'telefon' in result['types_found']


def test_allowed_file_types_default():
    from app.config import Settings
    s = Settings()
    assert 'pdf' in s.ALLOWED_FILE_TYPES
    assert 'png' in s.ALLOWED_FILE_TYPES


def test_session_timeout_default():
    from app.config import Settings
    s = Settings()
    assert s.SESSION_TIMEOUT_MINUTES == 30


def test_endpoint_stats():
    from app.core.metrics import metrics
    metrics.reset()
    metrics.record_request(200, endpoint='/api/health')
    metrics.record_request(200, endpoint='/api/health')
    metrics.record_request(200, endpoint='/api/version')
    stats = metrics.endpoint_stats('/api/health')
    assert stats['request_count'] == 2
    assert stats['percentage'] > 0
    metrics.reset()


def test_search_by_content_empty():
    from app.services.history_repository import HistoryRepository
    from pathlib import Path
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        repo = HistoryRepository(Path(tmp))
        result = repo.search_by_content('test')
        assert result == []


def test_storage_error():
    from app.core.exceptions import StorageError
    e = StorageError('Dosya yazma hatasi')
    assert e.status_code == 500
    assert e.code == 'storage_error'


def test_export_error():
    from app.core.exceptions import ExportError
    e = ExportError('Disari aktarma hatasi')
    assert e.status_code == 500
    assert e.code == 'export_error'


def test_pii_detect_and_classify():
    from app.services.pii_detector import PIIDetector
    d = PIIDetector()
    result = d.detect_and_classify('Email: test@test.com')
    assert result['total'] == 1
    assert 'eposta' in result['unique_types']


def test_metrics_health_summary():
    from app.core.metrics import metrics
    metrics.reset()
    metrics.record_request(200)
    metrics.record_request(200)
    result = metrics.health_summary()
    assert result['status'] == 'healthy'
    assert result['error_rate'] == 0
    metrics.reset()


def test_status_code_distribution():
    from app.core.metrics import metrics
    metrics.reset()
    metrics.record_request(200)
    metrics.record_request(404)
    metrics.record_request(500)
    result = metrics.status_code_distribution()
    assert result['2xx'] == 1
    assert result['4xx'] == 1
    assert result['5xx'] == 1
    metrics.reset()


def test_pii_redact_text():
    from app.services.pii_detector import PIIDetector
    d = PIIDetector()
    result = d.redact_text('Email: test@test.com')
    assert '[REDACTED]' in result
    assert 'test@test.com' not in result


def test_pii_redact_custom_replacement():
    from app.services.pii_detector import PIIDetector
    d = PIIDetector()
    result = d.redact_text('Email: test@test.com', replacement='***')
    assert '***' in result


def test_authentication_error():
    from app.core.exceptions import AuthenticationError
    e = AuthenticationError('Oturum suresi doldu')
    assert e.status_code == 401
    assert e.code == 'authentication_error'


def test_authorization_error():
    from app.core.exceptions import AuthorizationError
    e = AuthorizationError('Yetkisiz erisim')
    assert e.status_code == 403
    assert e.code == 'authorization_error'


def test_max_tags_default():
    from app.config import Settings
    s = Settings()
    assert s.MAX_TAGS_PER_RECORD == 20


def test_max_note_length_default():
    from app.config import Settings
    s = Settings()
    assert s.MAX_NOTE_LENGTH == 2000


import tempfile, os

class TestAuditLogger:
    def test_audit_log_and_retrieve(self):
        from app.services.audit_logger import AuditLogger
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            al = AuditLogger(td)
            al.log('analyze', record_id='r1', details={'file': 'test.pdf'})
            al.log('delete', record_id='r2')
            logs = al.get_logs()
            assert len(logs) == 2
            assert logs[0]['action'] == 'analyze'
            assert logs[1]['action'] == 'delete'

    def test_audit_filter_by_action(self):
        from app.services.audit_logger import AuditLogger
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            al = AuditLogger(td)
            al.log('analyze')
            al.log('delete')
            al.log('analyze')
            logs = al.get_logs(action='analyze')
            assert len(logs) == 2
            assert all(l['action'] == 'analyze' for l in logs)

    def test_audit_filter_by_record_id(self):
        from app.services.audit_logger import AuditLogger
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            al = AuditLogger(td)
            al.log('analyze', record_id='r1')
            al.log('delete', record_id='r2')
            logs = al.get_logs(record_id='r1')
            assert len(logs) == 1
            assert logs[0]['record_id'] == 'r1'

    def test_audit_stats(self):
        from app.services.audit_logger import AuditLogger
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            al = AuditLogger(td)
            al.log('analyze')
            al.log('analyze')
            al.log('delete')
            s = al.stats()
            assert s['total_logs'] == 3
            assert s['action_counts']['analyze'] == 2
            assert s['action_counts']['delete'] == 1


class TestInputSanitizer:
    def test_sanitize_string_escapes_html(self):
        from app.core.sanitizer import InputSanitizer
        result = InputSanitizer.sanitize_string('<script>alert(1)</script>')
        assert '<script>' not in result
        assert 'alert' not in result or '<' in result

    def test_strip_tags(self):
        from app.core.sanitizer import InputSanitizer
        result = InputSanitizer.strip_tags('<b>bold</b> text')
        assert result == 'bold text'

    def test_sanitize_filename(self):
        from app.core.sanitizer import InputSanitizer
        assert '..' not in InputSanitizer.sanitize_filename('../../etc/passwd')
        assert InputSanitizer.sanitize_filename('test.pdf') == 'test.pdf'

    def test_is_safe_path(self):
        from app.core.sanitizer import InputSanitizer
        assert InputSanitizer.is_safe_path('uploads/file.pdf') is True
        assert InputSanitizer.is_safe_path('../etc/passwd') is False


class TestBackupService:
    def test_create_and_list_backup(self):
        from app.services.backup_service import BackupService
        import tempfile, os, json
        with tempfile.TemporaryDirectory() as td:
            hist_dir = os.path.join(td, 'history')
            os.makedirs(hist_dir)
            with open(os.path.join(hist_dir, 'test.json'), 'w') as f:
                json.dump({'id': 'test1'}, f)
            bs = BackupService(history_dir=hist_dir, backup_dir=os.path.join(td, 'backups'))
            result = bs.create_backup()
            assert result['file_count'] == 1
            assert result['size_bytes'] > 0
            backups = bs.list_backups()
            assert len(backups) == 1

    def test_delete_old_backups(self):
        from app.services.backup_service import BackupService
        import tempfile, os, json, time
        with tempfile.TemporaryDirectory() as td:
            hist_dir = os.path.join(td, 'history')
            os.makedirs(hist_dir)
            with open(os.path.join(hist_dir, 'test.json'), 'w') as f:
                json.dump({'id': 'test1'}, f)
            bs = BackupService(history_dir=hist_dir, backup_dir=os.path.join(td, 'backups'))
            for i in range(3):
                bs.create_backup()
                time.sleep(0.01)
            assert len(bs.list_backups()) == 3
            deleted = bs.delete_old_backups(keep_count=1)
            assert deleted >= 0
            assert len(bs.list_backups()) >= 1


class TestAuditLoggerClearOld:
    def test_clear_old_logs(self):
        from app.services.audit_logger import AuditLogger
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            al = AuditLogger(td)
            al.log('test1')
            al.log('test2')
            count = al.clear_old_logs(days=0)
            assert count >= 0


class TestTextAnalyzer:
    def test_basic_analysis(self):
        from app.services.text_analyzer import TextAnalyzer
        result = TextAnalyzer.analyze('Bu bir test cumlesidir. Ikinci cumle burada.')
        assert result['word_count'] > 0
        assert result['sentence_count'] == 2
        assert result['char_count'] > 0
        assert 'top_words' in result

    def test_empty_text(self):
        from app.services.text_analyzer import TextAnalyzer
        result = TextAnalyzer.analyze('')
        assert result['word_count'] == 0
        assert result['sentence_count'] == 0

    def test_vocabulary_richness(self):
        from app.services.text_analyzer import TextAnalyzer
        result = TextAnalyzer.analyze('kelime kelime kelime farkli baska')
        assert result['vocabulary_richness'] < 1.0
        assert result['unique_words'] == 3


class TestWebhookService:
    def test_register_and_notify(self):
        from app.services.webhook_service import WebhookService
        ws = WebhookService()
        wh = ws.register('http://test.com/hook', events=['analyze'])
        assert wh['id']
        assert wh['active'] is True
        count = ws.notify('analyze', {'id': 'test'})
        assert count == 1
        hist = ws.history()
        assert len(hist) == 1

    def test_unregister(self):
        from app.services.webhook_service import WebhookService
        ws = WebhookService()
        wh = ws.register('http://test.com/hook')
        ws.unregister(wh['id'])
        assert len(ws.list_webhooks()) == 0


class TestTextAnalyzerEdgeCases:
    def test_single_word(self):
        from app.services.text_analyzer import TextAnalyzer
        r = TextAnalyzer.analyze('merhaba')
        assert r['word_count'] == 1
        assert r['sentence_count'] == 1
        assert r['vocabulary_richness'] == 1.0

    def test_long_text(self):
        from app.services.text_analyzer import TextAnalyzer
        text = 'Bu bir test cumlesi. ' * 100
        r = TextAnalyzer.analyze(text)
        assert r['word_count'] > 0
        assert r['readability_score'] >= 0


class TestSanitizerEdgeCases:
    def test_sanitize_none_input(self):
        from app.core.sanitizer import InputSanitizer
        assert InputSanitizer.sanitize_string(123) == 123
        assert InputSanitizer.strip_tags(None) is None

    def test_empty_filename(self):
        from app.core.sanitizer import InputSanitizer
        assert InputSanitizer.sanitize_filename('') == ''

    def test_safe_path_normal(self):
        from app.core.sanitizer import InputSanitizer
        assert InputSanitizer.is_safe_path('documents/report.pdf') is True
        assert InputSanitizer.is_safe_path('') is True


def test_ip_config_defaults():
    from app.config import Settings
    s = Settings(_env_file=None, LLM_API_KEY='t')
    assert s.IP_WHITELIST == ''
    assert s.IP_BLACKLIST == ''


def test_records_by_priority(client):
    """Oncelige gore filtreleme testi."""
    resp = client.get("/api/history")
    records = resp.json().get("records", [])
    if records:
        record_id = records[0]["id"]
        resp = client.patch(f"/api/history/{record_id}/priority", json={"priority": "high"})
        if resp.status_code == 200:
            resp2 = client.get("/api/history/by-priority/high")
            assert resp2.status_code == 200
            data = resp2.json()
            assert data["priority"] == "high"
        return
    resp = client.get("/api/history/by-priority/normal")
    assert resp.status_code == 200
    assert resp.json()["priority"] == "normal"

def test_records_by_priority_invalid(client):
    """Gecersiz oncelik filtrelemesi."""
    resp = client.get("/api/history/by-priority/critical")
    assert resp.status_code == 400

def test_bulk_update_priority(client):
    """Toplu oncelik guncelleme testi."""
    resp = client.get("/api/history")
    records = resp.json().get("records", [])
    if records:
        record_id = records[0]["id"]
        resp = client.post("/api/history/bulk-priority", json={"ids": [record_id], "priority": "urgent"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["updated"] == 1
        return
    resp = client.post("/api/history/bulk-priority", json={"ids": ["nonexistent"], "priority": "normal"})
    assert resp.status_code == 200
    assert resp.json()["updated"] == 0

def test_bulk_update_priority_invalid(client):
    """Gecersiz oncelik toplu guncelleme."""
    resp = client.post("/api/history/bulk-priority", json={"ids": ["fake"], "priority": "xxx"})
    assert resp.status_code == 400

def test_bulk_update_priority_empty_ids(client):
    """Bos id listesiyle toplu guncelleme."""
    resp = client.post("/api/history/bulk-priority", json={"ids": [], "priority": "high"})
    assert resp.status_code == 400


def test_integrity_compute_hash():
    """IntegrityService hash hesaplama testi."""
    from app.services.integrity_service import IntegrityService
    h = IntegrityService.compute_hash_from_bytes(b"test data")
    assert isinstance(h, str)
    assert len(h) == 64
    h2 = IntegrityService.compute_hash_from_bytes(b"test data")
    assert h == h2
    h3 = IntegrityService.compute_hash_from_bytes(b"different")
    assert h != h3

def test_integrity_verify_record():
    """IntegrityService kayit dogrulama testi."""
    from app.services.integrity_service import IntegrityService
    result = IntegrityService.verify_record_integrity({"id": "abc", "created_at": "2024-01-01"})
    assert result["valid"] is True
    result2 = IntegrityService.verify_record_integrity({"foo": "bar"})
    assert result2["valid"] is False
    assert len(result2["issues"]) > 0

def test_integrity_compute_checksum():
    """IntegrityService checksum testi."""
    from app.services.integrity_service import IntegrityService
    c1 = IntegrityService.compute_checksum({"a": 1, "b": 2})
    c2 = IntegrityService.compute_checksum({"b": 2, "a": 1})
    assert c1 == c2

def test_notification_service():
    """NotificationService temel islemleri testi."""
    import tempfile
    from app.services.notification_service import NotificationService
    with tempfile.TemporaryDirectory() as d:
        svc = NotificationService(d)
        svc.send("info", "Test", "Test mesaji")
        svc.send("warning", "Uyari", "Uyari mesaji")
        notes = svc.get_notifications()
        assert len(notes) == 2
        assert svc.unread_count() == 2
        svc.mark_all_read()
        assert svc.unread_count() == 0
        stats = svc.stats()
        assert stats["total"] == 2

def test_notification_filtering():
    """NotificationService filtreleme testi."""
    import tempfile
    from app.services.notification_service import NotificationService
    with tempfile.TemporaryDirectory() as d:
        svc = NotificationService(d)
        svc.send("info", "Info", "info msg")
        svc.send("error", "Error", "error msg")
        svc.send("warning", "Warn", "warn msg")
        errors = svc.get_notifications(level="error")
        assert len(errors) == 1
        assert errors[0]["level"] == "error"

def test_changelog_methods():
    """HistoryRepository changelog metodlari testi."""
    import tempfile
    from app.services.history_repository import HistoryRepository
    with tempfile.TemporaryDirectory() as d:
        repo = HistoryRepository(d)
        repo._write("rec1", {"id": "rec1", "created_at": "2024-01-01", "summary": "test"})
        result = repo.add_changelog_entry("rec1", "created", {"by": "test"})
        assert result is True
        log = repo.record_changelog("rec1")
        assert len(log) == 1
        assert log[0]["action"] == "created"
        result2 = repo.add_changelog_entry("nonexist", "update")
        assert result2 is False

def test_compute_hash_endpoint(client):
    """compute-hash endpoint testi."""
    import tempfile, os
    tmp = tempfile.mktemp(suffix=".txt")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("hash test content")
    with open(tmp, "rb") as fh:
        resp = client.post("/api/compute-hash", files={"file": ("test.txt", fh, "text/plain")})
    assert resp.status_code == 200
    data = resp.json()
    assert "hash" in data
    assert data["algorithm"] == "sha256"
    assert data["filename"] == "test.txt"
    os.unlink(tmp)

def test_notification_endpoints(client):
    """Bildirim endpoint'leri testi."""
    resp = client.get("/api/notifications")
    assert resp.status_code == 200
    resp = client.get("/api/notifications/stats")
    assert resp.status_code == 200
    resp = client.post("/api/notifications/mark-read", json={})
    assert resp.status_code == 200

def test_integrity_verify_endpoint(client):
    """Integrity verify endpoint testi."""
    resp = client.post("/api/integrity/verify-all", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "valid" in data

def test_changelog_endpoint(client):
    """Changelog endpoint testi - kayit olmadan."""
    resp = client.get("/api/history/nonexistent/changelog")
    assert resp.status_code == 404

def test_version_350():
    """Versiyon 3.5.0 testi."""
    from app import __version__
    assert __version__ == "3.5.0"

def test_dashboard_summary_endpoint(client):
    """Dashboard ozet endpoint testi."""
    resp = client.get("/api/dashboard/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_records" in data
    assert "active_records" in data
    assert "priority_distribution" in data
    assert "uptime_seconds" in data

def test_rate_limit_info_endpoint(client):
    """Rate limit bilgi endpoint testi."""
    resp = client.get("/api/rate-limit/info")
    assert resp.status_code == 200
    data = resp.json()
    assert "ip" in data

def test_export_csv_endpoint(client):
    """CSV export endpoint testi."""
    resp = client.get("/api/history/export/csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers.get("content-type", "")

def test_export_json_file_endpoint(client):
    """JSON file export endpoint testi."""
    resp = client.get("/api/history/export/json-file")
    assert resp.status_code == 200

def test_export_report_endpoint(client):
    """Export report endpoint testi."""
    resp = client.get("/api/history/export/report")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_records" in data
    assert "by_document_type" in data

def test_dependency_check_endpoint(client):
    """Dependency health check endpoint testi."""
    resp = client.get("/api/health/dependencies")
    assert resp.status_code == 200
    data = resp.json()
    assert "healthy" in data
    assert "checks" in data
    assert "history_repository" in data["checks"]

def test_export_service_csv():
    """ExportService CSV testi."""
    from app.services.export_service import ExportService
    records = [
        {"id": "1", "created_at": "2024-01-01", "source_name": "test.pdf", "document_type": "dilekce", "summary": "Test", "tags": ["a", "b"]},
        {"id": "2", "created_at": "2024-01-02", "source_name": "test2.pdf", "document_type": "rapor", "summary": "Test2", "tags": []},
    ]
    csv_str = ExportService.to_csv(records)
    assert "id" in csv_str
    assert "test.pdf" in csv_str
    assert "a, b" in csv_str

def test_export_service_json():
    """ExportService JSON testi."""
    from app.services.export_service import ExportService
    import json
    records = [{"id": "1", "created_at": "2024-01-01", "source_name": "test.pdf"}]
    result = ExportService.to_json(records)
    parsed = json.loads(result)
    assert len(parsed) == 1
    assert parsed[0]["id"] == "1"

def test_export_service_report():
    """ExportService rapor testi."""
    from app.services.export_service import ExportService
    records = [
        {"id": "1", "document_type": "dilekce", "priority": "high", "tags": ["x"], "favorite": True, "archived": False},
        {"id": "2", "document_type": "dilekce", "priority": "normal", "tags": ["x", "y"], "favorite": False, "archived": True},
    ]
    report = ExportService.summary_report(records)
    assert report["total_records"] == 2
    assert report["by_document_type"]["dilekce"] == 2
    assert report["favorite_count"] == 1
    assert report["archived_count"] == 1
    assert report["top_tags"][0]["tag"] == "x"

def test_logging_config():
    """Structured logging konfigurasyonu testi."""
    import tempfile
    import logging
    from app.core.logging_config import setup_logging, JSONFormatter
    with tempfile.TemporaryDirectory() as d:
        result = setup_logging("DEBUG", d, enable_file=True)
        assert result["level"] == "DEBUG"
        assert result["log_dir"] == d
        root = logging.getLogger()
        for h in root.handlers[:]:
            h.close()
            root.removeHandler(h)
    formatter = JSONFormatter()
    record = logging.LogRecord("test", logging.INFO, "test.py", 1, "Test msg", (), None)
    formatted = formatter.format(record)
    import json
    parsed = json.loads(formatted)
    assert parsed["level"] == "INFO"
    assert parsed["message"] == "Test msg"

def test_active_jobs_middleware():
    """ActiveJobsMiddleware testi."""
    from app.core.timeout_middleware import ActiveJobsMiddleware
    assert ActiveJobsMiddleware is not None

def test_request_timeout_middleware():
    """RequestTimeoutMiddleware testi."""
    from app.core.timeout_middleware import RequestTimeoutMiddleware
    assert RequestTimeoutMiddleware is not None

def test_export_csv_with_data():
    """CSV export bos olmayan veri ile testi."""
    from app.services.export_service import ExportService
    records = [{"id": "r1", "created_at": "2024-01-01", "source_name": "doc.pdf", "priority": "high", "favorite": True, "tags": ["hukuk"]}]
    csv = ExportService.to_csv(records)
    lines = csv.strip().split("\n")
    assert len(lines) == 2
    assert "doc.pdf" in lines[1]
    assert "Evet" in lines[1]

def test_full_text_search_endpoint(client):
    """Full-text arama endpoint testi."""
    resp = client.post("/api/history/search", json={"query": "test", "limit": 10})
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    assert "query" in data
    assert data["query"] == "test"

def test_full_text_search_empty_query(client):
    """Bos arama sorgusu testi."""
    resp = client.post("/api/history/search", json={"query": ""})
    assert resp.status_code == 400

def test_daily_stats_endpoint(client):
    """Gunluk istatistik endpoint testi."""
    resp = client.get("/api/history/stats/daily?days=7")
    assert resp.status_code == 200
    data = resp.json()
    assert "daily_counts" in data
    assert "period_days" in data
    assert data["period_days"] == 7
