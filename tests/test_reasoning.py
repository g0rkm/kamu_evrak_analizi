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
    """Uygulama versiyonu 4.1.0 olmalı."""
    from app import __version__
    assert __version__ == "4.1.0"


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
    records = resp.json().get("items", [])
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
    records = resp.json().get("items", [])
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
    """Versiyon 3.5.0 veya 3.7.0 testi."""
    from app import __version__
    assert __version__ == "4.1.0"

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
    assert 'total' in data
    assert 'categories' in data

def test_dependency_check_endpoint(client):
    """Dependency health check endpoint testi."""
    resp = client.get("/api/health/dependencies")
    assert resp.status_code == 200
    data = resp.json()
    assert "healthy" in data
    assert "checks" in data
    assert "history_repository" in data["checks"]

def test_export_service_csv():
    from app.services.export_service import ExportService
    svc = ExportService()
    records = [
        {"id": "1", "created_at": "2024-01-01", "source_name": "test.pdf", "document_type": "dilekce", "summary": "Test", "tags": ["a", "b"]},
        {"id": "2", "created_at": "2024-01-02", "source_name": "test2.pdf", "document_type": "rapor", "summary": "Test2", "tags": []},
    ]
    csv_str = svc.export_csv(records)
    assert "id" in csv_str
    assert "test.pdf" in csv_str

def test_export_service_json():
    from app.services.export_service import ExportService
    import json
    svc = ExportService()
    records = [{"id": "1", "created_at": "2024-01-01", "source_name": "test.pdf"}]
    result = svc.export_json(records)
    parsed = json.loads(result)
    assert len(parsed) == 1
    assert parsed[0]["id"] == "1"

def test_export_service_report():
    from app.services.export_service import ExportService
    svc = ExportService()
    records = [
        {"id": "1", "document_type": "dilekce", "priority": "high", "tags": ["x"], "favorite": True, "archived": False},
        {"id": "2", "document_type": "dilekce", "priority": "normal", "tags": ["x", "y"], "favorite": False, "archived": True},
    ]
    report = svc.export_summary(records)
    assert report["total"] == 2
    assert "categories" in report

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
    svc = ExportService()
    records = [{"id": "r1", "created_at": "2024-01-01", "source_name": "doc.pdf", "priority": "high", "favorite": True, "tags": ["hukuk"]}]
    csv = svc.export_csv(records)
    lines = csv.strip().split("\n")
    assert len(lines) == 2
    assert "doc.pdf" in lines[1]
    assert 'True' in lines[1]

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

def test_template_service():
    """TemplateService temel islemleri testi."""
    import tempfile
    from app.services.template_service import TemplateService
    with tempfile.TemporaryDirectory() as d:
        svc = TemplateService(d)
        templates = svc.list_templates()
        assert len(templates) >= 4
        tpl = svc.get_template("tpl_dilekce")
        assert tpl is not None
        assert tpl["name"] == "Dilekce"
        new_tpl = svc.create_template("Ozel Sablon", "ozel", description="Test sablonu", fields=["alan1"])
        assert new_tpl["id"].startswith("tpl_")
        assert not new_tpl["builtin"]
        deleted = svc.delete_template(new_tpl["id"])
        assert deleted is True
        deleted2 = svc.delete_template("tpl_dilekce")
        assert deleted2 is False

def test_template_update():
    """TemplateService guncelleme testi."""
    import tempfile
    from app.services.template_service import TemplateService
    with tempfile.TemporaryDirectory() as d:
        svc = TemplateService(d)
        tpl = svc.create_template("Guncelle", "test")
        updated = svc.update_template(tpl["id"], {"description": "guncellendi"})
        assert updated is not None
        assert updated["description"] == "guncellendi"
        builtin_update = svc.update_template("tpl_dilekce", {"description": "x"})
        assert builtin_update is None

def test_template_endpoints(client):
    """Template API endpoint'leri testi."""
    resp = client.get("/api/templates")
    assert resp.status_code == 200
    data = resp.json()
    assert "templates" in data
    assert len(data["templates"]) >= 4
    resp2 = client.get("/api/templates/tpl_dilekce")
    assert resp2.status_code == 200
    assert resp2.json()["name"] == "Dilekce"
    resp3 = client.post("/api/templates", json={"name": "Test Sablon", "document_type": "test"})
    assert resp3.status_code == 200
    tpl_id = resp3.json()["id"]
    resp4 = client.delete(f"/api/templates/{tpl_id}")
    assert resp4.status_code == 200

def test_template_not_found(client):
    """Olmayan sablon testi."""
    resp = client.get("/api/templates/nonexistent")
    assert resp.status_code == 404

def test_full_text_search_with_fields(client):
    """Full-text arama belirli alanlarla testi."""
    resp = client.post("/api/history/search", json={"query": "test", "fields": ["summary"], "limit": 5})
    assert resp.status_code == 200
    data = resp.json()
    assert data["query"] == "test"

def test_config_new_fields():
    """Yeni konfigürasyon alanlari testi."""
    from app.config import Settings
    s = Settings(_env_file=None, LLM_API_KEY="test")
    assert s.MAX_TEMPLATE_COUNT == 100
    assert s.ENABLE_NOTIFICATIONS is True
    assert s.AUTO_BACKUP_ENABLED is False
    assert s.AUTO_BACKUP_INTERVAL_HOURS == 24
    assert s.SESSION_TIMEOUT_MINUTES == 30

def test_integrity_compute_hash_file():
    """IntegrityService dosya hash testi."""
    import tempfile, os
    from app.services.integrity_service import IntegrityService
    tmp = tempfile.mktemp(suffix=".txt")
    with open(tmp, "w") as f:
        f.write("test data for hash")
    h = IntegrityService.compute_hash(tmp)
    assert h is not None
    assert len(h) == 64
    assert IntegrityService.verify_hash(tmp, h) is True
    assert IntegrityService.verify_hash(tmp, "wrong") is False
    os.unlink(tmp)
    assert IntegrityService.compute_hash(tmp) is None

def test_auth_service():
    """AuthService temel islemleri testi."""
    import tempfile
    from app.services.auth_service import AuthService
    with tempfile.TemporaryDirectory() as d:
        svc = AuthService(d)
        user = svc.create_user("testuser", "pass123", role="memur", full_name="Test User")
        assert user["username"] == "testuser"
        assert user["role"] == "memur"
        token = svc.authenticate("testuser", "pass123")
        assert token is not None
        info = svc.validate_token(token)
        assert info is not None
        assert info["username"] == "testuser"
        bad_token = svc.authenticate("testuser", "wrong")
        assert bad_token is None
        bad_user = svc.authenticate("nouser", "pass123")
        assert bad_user is None

def test_auth_permissions():
    """AuthService yetki kontrolu testi."""
    from app.services.auth_service import AuthService
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        svc = AuthService(d)
        assert svc.has_permission("admin", "system.admin") is True
        assert svc.has_permission("memur", "system.admin") is False
        assert svc.has_permission("memur", "record.create") is True
        assert svc.has_permission("izleyici", "record.create") is False
        assert svc.has_permission("izleyici", "record.read") is True

def test_auth_deactivate():
    """AuthService kullanici deaktivasyon testi."""
    import tempfile
    from app.services.auth_service import AuthService
    with tempfile.TemporaryDirectory() as d:
        svc = AuthService(d)
        svc.create_user("deactuser", "pass")
        assert svc.deactivate_user("deactuser") is True
        token = svc.authenticate("deactuser", "pass")
        assert token is None

def test_auth_endpoints(client):
    """Auth API endpoint'leri testi."""
    resp = client.post("/api/auth/register", json={"username": "apiuser", "password": "secret", "role": "memur"})
    assert resp.status_code == 200
    assert resp.json()["username"] == "apiuser"
    resp2 = client.post("/api/auth/login", json={"username": "apiuser", "password": "secret"})
    assert resp2.status_code == 200
    assert "token" in resp2.json()
    token = resp2.json()["token"]
    resp3 = client.post("/api/auth/validate", json={"token": token})
    assert resp3.status_code == 200
    assert resp3.json()["valid"] is True
    resp4 = client.get("/api/auth/roles")
    assert resp4.status_code == 200
    assert "admin" in resp4.json()["roles"]
    resp5 = client.get("/api/auth/permissions")
    assert resp5.status_code == 200
    assert "record.create" in resp5.json()["permissions"]

def test_auth_login_invalid(client):
    """Gecersiz giris denemesi testi."""
    resp = client.post("/api/auth/login", json={"username": "nouser", "password": "wrong"})
    assert resp.status_code == 403

def test_auth_duplicate_user(client):
    """Ayni kullanici tekrar kayit testi."""
    client.post("/api/auth/register", json={"username": "dupuser", "password": "pass"})
    resp = client.post("/api/auth/register", json={"username": "dupuser", "password": "pass2"})
    assert resp.status_code == 400

def test_auth_token_revoke():
    """AuthService token iptal testi."""
    import tempfile
    from app.services.auth_service import AuthService
    with tempfile.TemporaryDirectory() as d:
        svc = AuthService(d)
        svc.create_user("revokeuser", "pass")
        token = svc.authenticate("revokeuser", "pass")
        assert svc.validate_token(token) is not None
        assert svc.revoke_token(token) is True
        assert svc.validate_token(token) is None

def test_auth_list_users():
    """AuthService kullanici listeleme testi."""
    import tempfile
    from app.services.auth_service import AuthService
    with tempfile.TemporaryDirectory() as d:
        svc = AuthService(d)
        svc.create_user("user1", "pass1", role="memur")
        svc.create_user("user2", "pass2", role="yonetici")
        users = svc.list_users()
        assert len(users) == 2
        assert all("password_hash" not in u for u in users)

def test_version_360():
    """Versiyon 3.6.0 veya 3.7.0 testi."""
    from app import __version__
    assert __version__ == "4.1.0"

def test_scheduler_service():
    """SchedulerService temel islemleri testi."""
    from app.services.scheduler_service import SchedulerService
    svc = SchedulerService()
    counter = {"val": 0}
    def increment():
        counter["val"] += 1
    svc.add_task("counter", increment, 3600, enabled=True)
    tasks = svc.list_tasks()
    assert len(tasks) == 1
    assert tasks[0]["name"] == "counter"
    stats = svc.task_stats()
    assert stats["total_tasks"] == 1
    assert stats["active_tasks"] == 1
    assert svc.remove_task("counter") is True
    assert len(svc.list_tasks()) == 0

def test_scheduler_endpoints(client):
    """Scheduler API endpoint'leri testi."""
    resp = client.get("/api/scheduler/tasks")
    assert resp.status_code == 200
    assert "tasks" in resp.json()
    resp2 = client.get("/api/scheduler/stats")
    assert resp2.status_code == 200
    assert "total_tasks" in resp2.json()

def test_auth_roles_endpoint(client):
    """Auth roller endpoint testi."""
    resp = client.get("/api/auth/roles")
    assert resp.status_code == 200
    roles = resp.json()["roles"]
    assert "admin" in roles
    assert "memur" in roles
    assert "yonetici" in roles
    assert "izleyici" in roles

def test_auth_permissions_endpoint(client):
    """Auth izinler endpoint testi."""
    resp = client.get("/api/auth/permissions")
    assert resp.status_code == 200
    perms = resp.json()["permissions"]
    assert "record.create" in perms
    assert "system.admin" in perms


def test_scheduler_task_removal():
    """SchedulerService gorev kaldirma testi."""
    from app.services.scheduler_service import SchedulerService
    svc = SchedulerService()
    svc.add_task("temp", lambda: None, 60)
    assert len(svc.list_tasks()) == 1
    assert svc.remove_task("temp") is True
    assert svc.remove_task("nonexist") is False
    assert len(svc.list_tasks()) == 0


def test_migration_service():
    """MigrationService temel islemleri testi."""
    import tempfile
    from app.services.migration_service import MigrationService
    with tempfile.TemporaryDirectory() as d:
        svc = MigrationService(d)
        assert svc.get_current_version() == 1
        old_record = {"id": "r1", "created_at": "2024-01-01"}
        migrated = svc.migrate_record(old_record)
        assert migrated["priority"] == "normal"
        assert migrated["_schema_version"] == 2
        assert "tags" in migrated
        assert "changelog" in migrated

def test_migration_validate():
    """MigrationService dogrulama testi."""
    import tempfile
    from app.services.migration_service import MigrationService
    with tempfile.TemporaryDirectory() as d:
        svc = MigrationService(d)
        valid = {"id": "r1", "created_at": "2024-01-01"}
        result = svc.validate_record(valid)
        assert result["valid"] is True
        invalid = {"summary": "no id"}
        result2 = svc.validate_record(invalid)
        assert result2["valid"] is False

def test_migration_all():
    """MigrationService toplu migrasyon testi."""
    import tempfile
    from app.services.migration_service import MigrationService
    with tempfile.TemporaryDirectory() as d:
        svc = MigrationService(d)
        records = [
            {"id": "r1", "created_at": "2024-01-01"},
            {"id": "r2", "created_at": "2024-01-02", "_schema_version": 2},
        ]
        result = svc.migrate_all(records)
        assert result["migrated"] == 1
        assert result["errors"] == 0

def test_migration_status_endpoint(client):
    """Migration status endpoint testi."""
    resp = client.get("/api/migration/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "current_schema_version" in data or "error" in data

def test_migration_validate_endpoint(client):
    """Migration validate endpoint testi."""
    resp = client.post("/api/migration/validate", json={})
    assert resp.status_code == 200

def test_security_headers_middleware(client):
    """Guvenlik basliklari middleware testi."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("X-XSS-Protection") == "1; mode=block"

def test_migration_schema_report():
    """MigrationService sema raporu testi."""
    import tempfile
    from app.services.migration_service import MigrationService
    with tempfile.TemporaryDirectory() as d:
        svc = MigrationService(d)
        records = [
            {"id": "r1", "created_at": "2024-01-01"},
            {"id": "r2", "created_at": "2024-01-02", "_schema_version": 2},
        ]
        report = svc.schema_report(records)
        assert report["total_records"] == 2
        assert report["current_schema_version"] == 2

def test_version_370():
    from app import __version__
    assert __version__ == '4.1.0'

def test_config_report_endpoint(client):
    resp = client.get('/api/system/config-report')
    assert resp.status_code == 200
    data = resp.json()
    assert 'services' in data
    assert 'max_file_size_mb' in data

def test_system_environment_endpoint(client):
    resp = client.get('/api/system/environment')
    assert resp.status_code == 200
    assert 'python_version' in resp.json()

def test_api_summary_endpoint(client):
    resp = client.get('/api/api-summary')
    assert resp.status_code == 200
    data = resp.json()
    assert 'total_endpoints' in data
    assert data['total_endpoints'] > 0
    assert 'endpoints' in data

def test_system_uptime_endpoint(client):
    resp = client.get('/api/system/uptime')
    assert resp.status_code == 200
    data = resp.json()
    assert 'uptime_seconds' in data
    assert 'uptime_human' in data

def test_system_active_jobs_endpoint(client):
    resp = client.get('/api/system/active-jobs')
    assert resp.status_code == 200
    assert 'active_jobs' in resp.json()


class TestFileValidator:
    def test_valid_extension(self):
        from app.services.file_validator import FileValidator
        v = FileValidator()
        assert v.validate_extension("test.pdf") is True
        assert v.validate_extension("test.docx") is True
        assert v.validate_extension("test.exe") is False
        assert v.validate_extension("test.py") is False

    def test_validate_size(self):
        from app.services.file_validator import FileValidator
        v = FileValidator(max_file_size_mb=10)
        assert v.validate_size(5 * 1024 * 1024) is True
        assert v.validate_size(15 * 1024 * 1024) is False
        assert v.validate_size(0) is True
        assert v.validate_size(-1) is False

    def test_validate_filename(self):
        from app.services.file_validator import FileValidator
        v = FileValidator()
        assert v.validate_filename("test.pdf") == "test.pdf"
        assert v.validate_filename("../../etc/passwd") == "passwd"
        assert v.validate_filename("") == "unnamed_file"
        name = v.validate_filename("a" * 300 + ".pdf")
        assert len(name) <= 255

    def test_validate_full(self):
        from app.services.file_validator import FileValidator
        v = FileValidator(max_file_size_mb=10)
        result = v.validate("report.pdf", 1024)
        assert result["valid"] is True
        assert result["errors"] == []
        result2 = v.validate("script.exe", 1024)
        assert result2["valid"] is False
        assert len(result2["errors"]) > 0

    def test_file_type_label(self):
        from app.services.file_validator import FileValidator
        v = FileValidator()
        assert v.get_file_type_label("test.pdf") == "PDF Belgesi"
        assert v.get_file_type_label("test.docx") == "Word Belgesi"
        assert v.get_file_type_label("test.txt") == "Metin Dosyası"
        assert v.get_file_type_label("test.xlsx") == "Excel Tablosu"
        assert "Gorsel" in v.get_file_type_label("test.png") or "rsel" in v.get_file_type_label("test.png")


class TestSessionManager:
    def test_create_and_validate(self):
        from app.services.session_manager import SessionManager
        sm = SessionManager(timeout_minutes=30)
        session = sm.create_session("tok1", "admin", "admin")
        assert session["username"] == "admin"
        valid = sm.validate_session("tok1")
        assert valid is not None
        assert valid["username"] == "admin"

    def test_session_timeout(self):
        from app.services.session_manager import SessionManager
        from datetime import datetime, timezone, timedelta
        sm = SessionManager(timeout_minutes=1)
        sm.create_session("tok1", "user1", "memur")
        sm._sessions["tok1"]["last_activity"] = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        result = sm.validate_session("tok1")
        assert result is None

    def test_max_sessions_per_user(self):
        from app.services.session_manager import SessionManager
        sm = SessionManager(timeout_minutes=30, max_sessions_per_user=2)
        sm.create_session("t1", "user1", "memur")
        sm.create_session("t2", "user1", "memur")
        sm.create_session("t3", "user1", "memur")
        sessions = sm.get_active_sessions("user1")
        assert len(sessions) == 2

    def test_end_session(self):
        from app.services.session_manager import SessionManager
        sm = SessionManager()
        sm.create_session("tok1", "admin", "admin")
        assert sm.end_session("tok1") is True
        assert sm.end_session("tok1") is False
        assert sm.validate_session("tok1") is None

    def test_stats(self):
        from app.services.session_manager import SessionManager
        sm = SessionManager()
        sm.create_session("t1", "u1", "admin")
        sm.create_session("t2", "u2", "memur")
        stats = sm.stats()
        assert stats["total_active"] == 2
        assert stats["unique_users"] == 2


class TestHealthChecker:
    def test_check_disk(self):
        from app.services.health_checker import HealthChecker
        hc = HealthChecker()
        result = hc.check_disk()
        assert "free_mb" in result
        assert "total_mb" in result
        assert "used_percent" in result
        assert isinstance(result["warning"], bool)

    def test_check_python(self):
        from app.services.health_checker import HealthChecker
        hc = HealthChecker()
        result = hc.check_python()
        assert "version" in result
        assert "platform" in result
        assert "architecture" in result

    def test_check_service(self):
        from app.services.health_checker import HealthChecker
        hc = HealthChecker()
        result = hc.check_service("test", "some_obj")
        assert result["available"] is True
        assert result["name"] == "test"
        result2 = hc.check_service("empty", None)
        assert result2["available"] is False

    def test_check_all(self):
        from app.services.health_checker import HealthChecker
        hc = HealthChecker()
        result = hc.check_all({"svc1": "obj", "svc2": None})
        assert result["status"] in ("healthy", "degraded", "unhealthy")
        assert "disk" in result
        assert "memory" in result
        assert "services" in result
        assert result["services"]["svc1"]["available"] is True
        assert result["services"]["svc2"]["available"] is False


class TestNewEndpoints:
    def test_validate_file_endpoint(self, client):
        resp = client.post("/api/validate-file", json={"filename": "test.pdf", "file_size": 1024})
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True
        assert "file_type" in data

    def test_supported_file_types(self, client):
        resp = client.get("/api/supported-file-types")
        assert resp.status_code == 200
        data = resp.json()
        assert "extensions" in data
        assert ".pdf" in data["extensions"]
        assert "max_size_mb" in data

    def test_session_stats(self, client):
        resp = client.get("/api/sessions/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_active" in data

    def test_active_sessions(self, client):
        resp = client.get("/api/sessions/active")
        assert resp.status_code == 200
        data = resp.json()
        assert "sessions" in data
        assert "count" in data

    def test_cleanup_sessions(self, client):
        resp = client.post("/api/sessions/cleanup", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert "removed" in data

    def test_comprehensive_health(self, client):
        resp = client.get("/api/system/health-check")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("healthy", "degraded", "unhealthy")
        assert "disk" in data
        assert "services" in data

    def test_health_directories(self, client):
        resp = client.get("/api/system/directories")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)


class TestRetryService:
    def test_execute_success(self):
        from app.services.retry_service import RetryService
        rs = RetryService()
        result = rs.execute(lambda: 42)
        assert result == 42
        assert rs.stats()["total_successes"] == 1

    def test_execute_with_retries(self):
        from app.services.retry_service import RetryService, RetryConfig
        call_count = 0
        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("fail")
            return "ok"
        config = RetryConfig(max_retries=3, base_delay=0.01, jitter=False)
        rs = RetryService(config)
        result = rs.execute(flaky)
        assert result == "ok"
        assert call_count == 3
        assert rs.stats()["total_retries"] == 2

    def test_execute_all_fail(self):
        from app.services.retry_service import RetryService, RetryConfig
        import pytest
        config = RetryConfig(max_retries=2, base_delay=0.01, jitter=False)
        rs = RetryService(config)
        with pytest.raises(ValueError):
            rs.execute(lambda: (_ for _ in ()).throw(ValueError("always fail")))
        assert rs.stats()["total_failures"] == 1

    def test_with_retry_decorator(self):
        from app.services.retry_service import with_retry
        call_count = 0
        @with_retry(max_retries=2, base_delay=0.01, retryable_exceptions=(ValueError,))
        def my_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("once")
            return "done"
        result = my_func()
        assert result == "done"
        assert call_count == 2


class TestCacheService:
    def test_set_and_get(self):
        from app.services.cache_service import CacheService
        cs = CacheService()
        cs.set("key1", "value1")
        assert cs.get("key1") == "value1"
        assert cs.get("nonexistent") is None

    def test_expiration(self):
        import time
        from app.services.cache_service import CacheService
        cs = CacheService(default_ttl=0.1)
        cs.set("k", "v")
        assert cs.get("k") == "v"
        time.sleep(0.15)
        assert cs.get("k") is None

    def test_max_size(self):
        from app.services.cache_service import CacheService
        cs = CacheService(max_size=3)
        cs.set("a", 1)
        cs.set("b", 2)
        cs.set("c", 3)
        cs.set("d", 4)
        assert cs.get("a") is None
        assert cs.get("d") == 4
        assert cs.stats()["size"] == 3

    def test_delete(self):
        from app.services.cache_service import CacheService
        cs = CacheService()
        cs.set("k", "v")
        assert cs.delete("k") is True
        assert cs.delete("k") is False
        assert cs.get("k") is None

    def test_clear(self):
        from app.services.cache_service import CacheService
        cs = CacheService()
        cs.set("a", 1)
        cs.set("b", 2)
        cs.clear()
        assert cs.stats()["size"] == 0

    def test_get_or_set(self):
        from app.services.cache_service import CacheService
        cs = CacheService()
        result = cs.get_or_set("k", lambda: "computed")
        assert result == "computed"
        result2 = cs.get_or_set("k", lambda: "other")
        assert result2 == "computed"

    def test_stats(self):
        from app.services.cache_service import CacheService
        cs = CacheService()
        cs.set("a", 1)
        cs.get("a")
        cs.get("miss")
        stats = cs.stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["size"] == 1


class TestCacheRetryEndpoints:
    def test_cache_stats_endpoint(self, client):
        resp = client.get("/api/system/cache-stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "size" in data
        assert "hits" in data

    def test_clear_cache_endpoint(self, client):
        resp = client.post("/api/system/cache-clear", json={})
        assert resp.status_code == 200
        assert resp.json()["status"] == "cleared"

    def test_retry_stats_endpoint(self, client):
        resp = client.get("/api/system/retry-stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_calls" in data


class TestIPFilterMiddleware:
    def test_parse_ips(self):
        from app.core.ip_filter_middleware import IPFilterMiddleware
        # Bos uygulama nesnesi olusturmak icin basit bir asgi app kullaniyoruz
        async def dummy_app(scope, receive, send):
            pass
        mw = IPFilterMiddleware(dummy_app, whitelist="192.168.1.1, 10.0.0.1", blacklist="172.16.0.1")
        assert "192.168.1.1" in mw.whitelist
        assert "10.0.0.1" in mw.whitelist
        assert "172.16.0.1" in mw.blacklist

    def test_empty_whitelist_allows_all(self):
        from app.core.ip_filter_middleware import IPFilterMiddleware
        async def dummy_app(scope, receive, send):
            pass
        mw = IPFilterMiddleware(dummy_app, whitelist="", blacklist="")
        assert mw._is_allowed("1.2.3.4") is True

    def test_blacklist_blocks(self):
        from app.core.ip_filter_middleware import IPFilterMiddleware
        async def dummy_app(scope, receive, send):
            pass
        mw = IPFilterMiddleware(dummy_app, whitelist="", blacklist="1.2.3.4")
        assert mw._is_allowed("1.2.3.4") is False
        assert mw._is_allowed("5.6.7.8") is True

    def test_whitelist_only_allows_listed(self):
        from app.core.ip_filter_middleware import IPFilterMiddleware
        async def dummy_app(scope, receive, send):
            pass
        mw = IPFilterMiddleware(dummy_app, whitelist="10.0.0.1", blacklist="")
        assert mw._is_allowed("10.0.0.1") is True
        assert mw._is_allowed("10.0.0.2") is False


class TestBulkOperations:
    def test_bulk_delete(self, client):
        resp = client.get("/api/history")
        records = resp.json().get("items", [])
        if not records:
            return
        record_id = records[0]["id"]
        
        # Toplu silme
        resp = client.post("/api/history/bulk-delete", json={"ids": [record_id, "nonexistent"]})
        assert resp.status_code == 200
        data = resp.json()
        assert data["deleted"] == 1
        assert data["not_found"] == 1

    def test_bulk_delete_empty_ids(self, client):
        resp = client.post("/api/history/bulk-delete", json={"ids": []})
        assert resp.status_code in (400, 422)

    def test_bulk_archive(self, client):
        resp = client.get("/api/history")
        records = resp.json().get("items", [])
        if not records:
            return
        record_id = records[0]["id"]
        
        resp = client.post("/api/history/bulk-archive", json={"ids": [record_id], "archive": True})
        assert resp.status_code == 200
        data = resp.json()
        assert data["updated"] == 1
        assert data["archive"] is True

    def test_bulk_tag(self, client):
        resp = client.get("/api/history")
        records = resp.json().get("items", [])
        if not records:
            return
        record_id = records[0]["id"]
        
        resp = client.post("/api/history/bulk-tag", json={"ids": [record_id], "tags": ["onemli", "acil"]})
        assert resp.status_code == 200
        data = resp.json()
        assert data["updated"] == 1
        assert "onemli" in data["tags_added"]

    def test_bulk_tag_empty_tags(self, client):
        resp = client.post("/api/history/bulk-tag", json={"ids": ["x"], "tags": []})
        assert resp.status_code in (400, 422)


class TestMetricsEndpoints:
    def test_metrics_summary(self, client):
        resp = client.get("/api/metrics/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_requests" in data

    def test_metrics_endpoints(self, client):
        client.get("/api/health")
        resp = client.get("/api/metrics/endpoints")
        assert resp.status_code == 200
        data = resp.json()
        assert "endpoints" in data

    def test_metrics_top_endpoints(self, client):
        resp = client.get("/api/metrics/top-endpoints")
        assert resp.status_code == 200
        data = resp.json()
        assert "top" in data
        assert isinstance(data["top"], list)

    def test_metrics_slowest(self, client):
        resp = client.get("/api/metrics/slowest")
        assert resp.status_code == 200
        data = resp.json()
        assert "slowest" in data
        assert isinstance(data["slowest"], list)

    def test_metrics_status_distribution(self, client):
        resp = client.get("/api/metrics/status-distribution")
        assert resp.status_code == 200

    def test_metrics_records_requests(self, client):
        """MetricsMiddleware istekleri kaydediyor mu kontrol et"""
        for _ in range(3):
            client.get("/api/health")
        resp = client.get("/api/metrics/summary")
        data = resp.json()
        assert data["total_requests"] >= 3

    def test_config_report_includes_metrics(self, client):
        resp = client.get("/api/system/config-report")
        assert resp.status_code == 200
        data = resp.json()
        assert "metrics" in data["services"]
        assert data["services"]["metrics"] is True


class TestLogService:
    def test_log_stats(self, client):
        resp = client.get("/api/logs/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "recent_in_memory" in data
        assert "log_files" in data

    def test_log_files(self, client):
        resp = client.get("/api/logs/files")
        assert resp.status_code == 200
        data = resp.json()
        assert "files" in data

    def test_recent_logs(self, client):
        resp = client.get("/api/logs/recent")
        assert resp.status_code == 200
        data = resp.json()
        assert "logs" in data

    def test_cleanup_logs(self, client):
        resp = client.post("/api/logs/cleanup", json={"days": 30}, headers={"Content-Type": "application/json"})
        assert resp.status_code == 200
        data = resp.json()
        assert "removed_files" in data

class TestVersionUpdate:
    def test_version_is_4_0_0(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == "4.1.0"

class TestExportEndpoints:
    def test_export_summary(self, client):
        resp = client.get("/api/data-export/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "categories" in data

    def test_export_json(self, client):
        resp = client.get("/api/data-export/json")
        assert resp.status_code == 200
        data = resp.json()
        assert "records" in data
        assert "count" in data

    def test_export_csv(self, client):
        resp = client.get("/api/data-export/csv")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers.get("content-type", "")

    def test_config_report_includes_export(self, client):
        resp = client.get("/api/system/config-report")
        assert resp.status_code == 200
        data = resp.json()
        assert "export_service" in data["services"]
        assert data["services"]["export_service"] is True

class TestBodyLimitMiddleware:
    def test_small_request_passes(self, client):
        resp = client.post("/api/analyze/text", json={"text": "test metin"}, headers={"Content-Type": "application/json"})
        assert resp.status_code != 413

    def test_content_length_header_check(self, client):
        resp = client.post("/api/analyze/text", json={"text": "a"}, headers={"Content-Type": "application/json", "Content-Length": "999999999999"})
        assert resp.status_code == 413


class TestMaintenanceEndpoints:
    def test_maintenance_status(self, client):
        resp = client.get("/api/maintenance/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "maintenance_mode" in data
        assert data["maintenance_mode"] is False

    def test_enable_disable_maintenance(self, client):
        resp = client.post("/api/maintenance/enable", json={"reason": "Sistem guncelleme"}, headers={"Content-Type": "application/json"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["maintenance_mode"] is True
        assert data["reason"] == "Sistem guncelleme"
        resp2 = client.post("/api/maintenance/disable", json={}, headers={"Content-Type": "application/json"})
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["maintenance_mode"] is False

    def test_maintenance_history(self, client):
        client.post("/api/maintenance/enable", json={"reason": "test"}, headers={"Content-Type": "application/json"})
        client.post("/api/maintenance/disable", json={}, headers={"Content-Type": "application/json"})
        resp = client.get("/api/maintenance/history")
        assert resp.status_code == 200
        data = resp.json()
        assert "history" in data
        assert len(data["history"]) >= 2

class TestLogServiceEndpoints:
    def test_log_service_in_config(self, client):
        resp = client.get("/api/system/config-report")
        assert resp.status_code == 200
        data = resp.json()
        assert data["services"]["log_service"] is True
        assert data["services"]["maintenance"] is True


class TestErrorTracker:
    def test_error_summary(self, client):
        resp = client.get("/api/errors/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_errors" in data
        assert "error_types" in data

    def test_recent_errors(self, client):
        resp = client.get("/api/errors/recent")
        assert resp.status_code == 200
        data = resp.json()
        assert "errors" in data

    def test_top_errors(self, client):
        resp = client.get("/api/errors/top")
        assert resp.status_code == 200
        data = resp.json()
        assert "top" in data

    def test_error_tracking_on_404(self, client):
        client.get("/api/nonexistent-endpoint-xyz")
        resp = client.get("/api/errors/summary")
        data = resp.json()
        assert data["total_errors"] >= 1
        assert "404" in data["error_types"]

    def test_clear_errors(self, client):
        client.get("/api/nonexistent-endpoint-xyz")
        resp = client.post("/api/errors/clear", json={}, headers={"Content-Type": "application/json"})
        assert resp.status_code == 200
        resp2 = client.get("/api/errors/summary")
        assert resp2.json()["total_errors"] == 0


class TestSystemDashboard:
    def test_service_count(self, client):
        resp = client.get("/api/system/service-count")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_services" in data
        assert "active_services" in data
        assert data["active_services"] > 0

    def test_full_status(self, client):
        resp = client.get("/api/system/full-status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "uptime_seconds" in data
        assert "services" in data
        assert "metrics" in data

    def test_correlation_stats(self, client):
        resp = client.get("/api/correlation/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "tracked_requests" in data

    def test_correlation_recent(self, client):
        resp = client.get("/api/correlation/recent")
        assert resp.status_code == 200
        data = resp.json()
        assert "requests" in data


class TestSanitizerService:
    def test_sanitize_html_escapes(self):
        from app.services.sanitizer import Sanitizer
        s = Sanitizer()
        result = s.sanitize_html('<script>alert("xss")</script>')
        assert "<script>" not in result

    def test_check_xss_detects_script(self):
        from app.services.sanitizer import Sanitizer
        s = Sanitizer()
        result = s.check_xss('<script>alert(1)</script>')
        assert result["safe"] is False
        assert len(result["threats"]) > 0

    def test_check_xss_safe_text(self):
        from app.services.sanitizer import Sanitizer
        s = Sanitizer()
        result = s.check_xss("Normal metin")
        assert result["safe"] is True
        assert result["threats"] == []

    def test_check_sql_injection(self):
        from app.services.sanitizer import Sanitizer
        s = Sanitizer()
        result = s.check_sql_injection("' OR 1=1")
        assert result["safe"] is False

    def test_check_sql_safe(self):
        from app.services.sanitizer import Sanitizer
        s = Sanitizer()
        result = s.check_sql_injection("SELECT ismi FROM tablo")
        assert result["safe"] is True

    def test_sanitize_input_combined(self):
        from app.services.sanitizer import Sanitizer
        s = Sanitizer()
        result = s.sanitize_input('<script>alert(1)</script>')
        assert result["safe"] is False
        assert "&lt;script&gt;" in result["sanitized"]

    def test_sanitize_filename(self):
        from app.services.sanitizer import Sanitizer
        s = Sanitizer()
        assert s.sanitize_filename("test<>.pdf") == "test.pdf"
        assert s.sanitize_filename("") == "unnamed"
        assert s.sanitize_filename("normal.txt") == "normal.txt"

    def test_sanitize_input_empty(self):
        from app.services.sanitizer import Sanitizer
        s = Sanitizer()
        result = s.sanitize_input("")
        assert result["safe"] is True


class TestSanitizerEndpoints:
    def test_sanitize_check_safe(self, client):
        resp = client.post("/api/sanitize/check", json={"text": "Guvenli metin"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["safe"] is True

    def test_sanitize_check_xss(self, client):
        resp = client.post("/api/sanitize/check", json={"text": "<script>alert(1)</script>"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["safe"] is False
        assert len(data["threats"]) > 0

    def test_sanitize_filename_endpoint(self, client):
        resp = client.post("/api/sanitize/filename", json={"filename": "test<script>.pdf"})
        assert resp.status_code == 200
        data = resp.json()
        assert "<script>" not in data["sanitized"]

    def test_sanitize_html_endpoint(self, client):
        resp = client.post("/api/sanitize/html", json={"text": "<b>bold</b>"})
        assert resp.status_code == 200
        data = resp.json()
        assert "&lt;b&gt;" in data["sanitized"]


class TestRequestValidator:
    def test_validate_text_valid(self):
        from app.services.request_validator import RequestValidator
        rv = RequestValidator()
        result = rv.validate_text("Gecerli metin")
        assert result["valid"] is True

    def test_validate_text_none(self):
        from app.services.request_validator import RequestValidator
        rv = RequestValidator()
        result = rv.validate_text(None)
        assert result["valid"] is False

    def test_validate_text_empty(self):
        from app.services.request_validator import RequestValidator
        rv = RequestValidator()
        result = rv.validate_text("")
        assert result["valid"] is False

    def test_validate_text_too_long(self):
        from app.services.request_validator import RequestValidator
        rv = RequestValidator()
        result = rv.validate_text("a" * 200000)
        assert result["valid"] is False

    def test_validate_pagination_valid(self):
        from app.services.request_validator import RequestValidator
        rv = RequestValidator()
        result = rv.validate_pagination(0, 20)
        assert result["valid"] is True

    def test_validate_pagination_invalid(self):
        from app.services.request_validator import RequestValidator
        rv = RequestValidator()
        result = rv.validate_pagination(-1, 0)
        assert result["valid"] is False

    def test_validate_id_valid(self):
        from app.services.request_validator import RequestValidator
        rv = RequestValidator()
        result = rv.validate_id("abc-123")
        assert result["valid"] is True

    def test_validate_id_invalid(self):
        from app.services.request_validator import RequestValidator
        rv = RequestValidator()
        result = rv.validate_id("abc<script>")
        assert result["valid"] is False

    def test_validate_ids(self):
        from app.services.request_validator import RequestValidator
        rv = RequestValidator()
        result = rv.validate_ids(["id1", "id2"])
        assert result["valid"] is True

    def test_validate_date_range_valid(self):
        from app.services.request_validator import RequestValidator
        rv = RequestValidator()
        result = rv.validate_date_range("2024-01-01", "2024-12-31")
        assert result["valid"] is True

    def test_validate_date_range_invalid(self):
        from app.services.request_validator import RequestValidator
        rv = RequestValidator()
        result = rv.validate_date_range("2024-12-31", "2024-01-01")
        assert result["valid"] is False


class TestHealthMonitor:
    def test_initial_status(self):
        from app.services.health_monitor import HealthMonitor
        hm = HealthMonitor()
        status = hm.get_status()
        assert status["status"] == "healthy"

    def test_register_and_run(self):
        from app.services.health_monitor import HealthMonitor
        hm = HealthMonitor()
        hm.register_check("test_check", lambda: True)
        result = hm.run_checks()
        assert result["status"] == "healthy"
        assert "test_check" in result["results"]

    def test_failing_check(self):
        from app.services.health_monitor import HealthMonitor
        hm = HealthMonitor()
        hm.register_check("bad", lambda: False)
        result = hm.run_checks()
        assert result["status"] == "degraded"
        assert hm.is_healthy() is False

    def test_history(self):
        from app.services.health_monitor import HealthMonitor
        hm = HealthMonitor()
        hm.register_check("ok", lambda: True)
        hm.run_checks()
        hm.run_checks()
        history = hm.get_history()
        assert len(history) == 2


class TestValidationEndpoints:
    def test_validate_text_endpoint(self, client):
        resp = client.post("/api/validate/text", json={"text": "Gecerli metin"})
        assert resp.status_code == 200
        assert resp.json()["valid"] is True

    def test_validate_pagination_endpoint(self, client):
        resp = client.post("/api/validate/pagination", json={"offset": 0, "limit": 20})
        assert resp.status_code == 200
        assert resp.json()["valid"] is True

    def test_validate_ids_endpoint(self, client):
        resp = client.post("/api/validate/ids", json={"ids": ["id1"]})
        assert resp.status_code == 200
        assert resp.json()["valid"] is True

    def test_health_monitor_status(self, client):
        resp = client.get("/api/health-monitor/status")
        assert resp.status_code == 200
        assert "status" in resp.json()

    def test_health_monitor_run(self, client):
        resp = client.post("/api/health-monitor/run", json={})
        assert resp.status_code == 200

    def test_health_monitor_history(self, client):
        resp = client.get("/api/health-monitor/history")
        assert resp.status_code == 200
        assert "history" in resp.json()


class TestPerformanceProfiler:
    def test_profiler_record_and_summary(self):
        from app.services.performance_profiler import PerformanceProfiler
        pp = PerformanceProfiler(slow_threshold_ms=100)
        pp.record("GET", "/api/test", 50.0)
        pp.record("GET", "/api/test", 150.0)
        summary = pp.get_summary()
        assert summary["total_profiled"] == 2
        assert summary["slow_requests_count"] == 1

    def test_profiler_slow_requests(self):
        from app.services.performance_profiler import PerformanceProfiler
        pp = PerformanceProfiler(slow_threshold_ms=100)
        pp.record("GET", "/api/slow", 500.0)
        slow = pp.get_slow_requests()
        assert len(slow) == 1
        assert slow[0]["path"] == "/api/slow"

    def test_profiler_endpoint_stats(self):
        from app.services.performance_profiler import PerformanceProfiler
        pp = PerformanceProfiler()
        pp.record("GET", "/api/test", 10.0)
        pp.record("GET", "/api/test", 20.0)
        profile = pp.get_endpoint_profile()
        assert "GET /api/test" in profile
        stats = profile["GET /api/test"]
        assert stats["count"] == 2
        assert stats["avg_ms"] == 15.0

    def test_profiler_reset(self):
        from app.services.performance_profiler import PerformanceProfiler
        pp = PerformanceProfiler()
        pp.record("GET", "/api/test", 10.0)
        pp.reset()
        assert pp.get_summary()["total_profiled"] == 0


class TestProfilerEndpoints:
    def test_profiler_summary_endpoint(self, client):
        resp = client.get("/api/profiler/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_profiled" in data

    def test_profiler_slow_requests_endpoint(self, client):
        resp = client.get("/api/profiler/slow-requests")
        assert resp.status_code == 200

    def test_profiler_endpoints_endpoint(self, client):
        resp = client.get("/api/profiler/endpoints")
        assert resp.status_code == 200

    def test_profiler_reset_endpoint(self, client):
        resp = client.post("/api/profiler/reset", json={})
        assert resp.status_code == 200
        assert resp.json()["status"] == "reset"


class TestWebhookRetry:
    def test_send_success(self):
        from app.services.webhook_retry import WebhookRetry
        wr = WebhookRetry()
        result = wr.send_with_retry("http://test.com", {"data": 1}, lambda u, p: "ok")
        assert result["success"] is True
        assert result["attempts"] == 1

    def test_send_failure_then_success(self):
        from app.services.webhook_retry import WebhookRetry
        wr = WebhookRetry(max_retries=2, base_delay=0.01)
        call_count = [0]
        def flaky_fn(url, payload):
            call_count[0] += 1
            if call_count[0] < 2:
                raise Exception("fail")
            return "ok"
        result = wr.send_with_retry("http://test.com", {}, flaky_fn)
        assert result["success"] is True
        assert result["attempts"] == 2

    def test_send_all_fail(self):
        from app.services.webhook_retry import WebhookRetry
        wr = WebhookRetry(max_retries=1, base_delay=0.01)
        result = wr.send_with_retry("http://test.com", {}, lambda u, p: (_ for _ in ()).throw(Exception("fail")))
        assert result["success"] is False

    def test_queue_and_stats(self):
        from app.services.webhook_retry import WebhookRetry
        wr = WebhookRetry()
        wr.queue_webhook("http://test.com", {"data": 1})
        stats = wr.get_stats()
        assert stats["pending_count"] == 1


class TestBackupVerifier:
    def test_verify_nonexistent(self):
        from app.services.backup_verifier import BackupVerifier
        bv = BackupVerifier()
        result = bv.verify_backup("/nonexistent/path.json")
        assert result["valid"] is False
        assert len(result["errors"]) > 0

    def test_verify_valid_json(self, tmp_path):
        import json
        from app.services.backup_verifier import BackupVerifier
        bv = BackupVerifier()
        f = tmp_path / "test_backup.json"
        f.write_text(json.dumps([{"id": "1"}]))
        result = bv.verify_backup(str(f))
        assert result["valid"] is True
        assert result["record_count"] == 1

    def test_stats(self):
        from app.services.backup_verifier import BackupVerifier
        bv = BackupVerifier()
        bv.verify_backup("/nonexistent.json")
        stats = bv.stats()
        assert stats["total_verifications"] == 1
        assert stats["invalid_count"] == 1

    def test_list_backups_empty(self):
        from app.services.backup_verifier import BackupVerifier
        bv = BackupVerifier(backup_dir="/nonexistent_dir")
        assert bv.list_backups() == []


class TestWebhookBackupEndpoints:
    def test_webhook_retry_stats(self, client):
        resp = client.get("/api/webhooks/retry-stats")
        assert resp.status_code == 200

    def test_webhook_retry_history(self, client):
        resp = client.get("/api/webhooks/retry-history")
        assert resp.status_code == 200

    def test_backup_list(self, client):
        resp = client.get("/api/backups/list")
        assert resp.status_code == 200

    def test_backup_stats(self, client):
        resp = client.get("/api/backups/stats")
        assert resp.status_code == 200

    def test_backup_verification_history(self, client):
        resp = client.get("/api/backups/verification-history")
        assert resp.status_code == 200


class TestDataEncryption:
    def test_encrypt_decrypt(self):
        from app.services.data_encryption import DataEncryption
        enc = DataEncryption(secret_key="test-key")
        original = "Hassas veri"
        encrypted = enc.encrypt(original)
        assert encrypted != original
        decrypted = enc.decrypt(encrypted)
        assert decrypted == original

    def test_compute_hash(self):
        from app.services.data_encryption import DataEncryption
        enc = DataEncryption()
        h = enc.compute_hash("test data")
        assert len(h) == 64

    def test_verify_hash(self):
        from app.services.data_encryption import DataEncryption
        enc = DataEncryption()
        h = enc.compute_hash("test data")
        assert enc.verify_hash("test data", h) is True
        assert enc.verify_hash("wrong data", h) is False

    def test_empty_encrypt(self):
        from app.services.data_encryption import DataEncryption
        enc = DataEncryption()
        assert enc.encrypt("") == ""
        assert enc.decrypt("") == ""

    def test_stats(self):
        from app.services.data_encryption import DataEncryption
        enc = DataEncryption()
        enc.encrypt("test")
        enc.compute_hash("test")
        stats = enc.get_stats()
        assert stats["encrypted"] == 1
        assert stats["hash_computed"] == 1


class TestEncryptionEndpoints:
    def test_hash_endpoint(self, client):
        resp = client.post("/api/encryption/hash", json={"data": "test"})
        assert resp.status_code == 200
        data = resp.json()
        assert "hash" in data
        assert len(data["hash"]) == 64

    def test_verify_hash_endpoint(self, client):
        resp1 = client.post("/api/encryption/hash", json={"data": "test"})
        h = resp1.json()["hash"]
        resp2 = client.post("/api/encryption/verify-hash", json={"data": "test", "hash": h})
        assert resp2.status_code == 200
        assert resp2.json()["valid"] is True

    def test_encryption_stats(self, client):
        resp = client.get("/api/encryption/stats")
        assert resp.status_code == 200


class TestSystemDiagnostics:
    def test_system_info(self):
        from app.services.system_diagnostics import SystemDiagnostics
        sd = SystemDiagnostics()
        info = sd.get_system_info()
        assert "python_version" in info
        assert "pid" in info
        assert info["pid"] > 0

    def test_disk_usage(self):
        from app.services.system_diagnostics import SystemDiagnostics
        sd = SystemDiagnostics()
        disk = sd.get_disk_usage(".")
        assert "total_gb" in disk
        assert disk["total_gb"] > 0

    def test_full_diagnostics(self):
        from app.services.system_diagnostics import SystemDiagnostics
        sd = SystemDiagnostics()
        diag = sd.get_full_diagnostics()
        assert "system" in diag
        assert "disk" in diag
        assert "timestamp" in diag


class TestDiagnosticsEndpoints:
    def test_diagnostics_system(self, client):
        resp = client.get("/api/diagnostics/system")
        assert resp.status_code == 200
        assert "python_version" in resp.json()

    def test_diagnostics_disk(self, client):
        resp = client.get("/api/diagnostics/disk")
        assert resp.status_code == 200

    def test_diagnostics_full(self, client):
        resp = client.get("/api/diagnostics/full")
        assert resp.status_code == 200
        data = resp.json()
        assert "system" in data
        assert "disk" in data

