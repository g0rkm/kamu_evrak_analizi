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
    assert is_valid_tc_kimlik("10000000146")
    assert not is_valid_tc_kimlik("12345678901")
    findings = PIIDetector().detect("TC: 10000000146, e-posta: ornek@kurum.gov.tr")
    assert {f.type for f in findings} == {"tc_kimlik", "eposta"}
    assert all("***" in f.masked_value for f in findings)


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
    assert "</evrak>" not in result
    assert "<evrak>" in result  # Sadece dıştaki etiketler kalmalı
    assert "[etiket]" in result


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
