import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402

SAMPLE_PETITION = """T.C.
ÖRNEK BELEDİYE BAŞKANLIĞINA

Konu: Kaldırım onarımı talebi

Mahallemizdeki kaldırımların bozuk olması nedeniyle yaşlı vatandaşlar zorluk çekmektedir.
Gerekli onarımın yapılması hususunda dilekçemin işleme alınmasını rica ederim.
Başvurum ile ilgili bilgi için 0532 123 45 67 numaralı telefondan ulaşabilirsiniz.

12.03.2026
Ayşe Yılmaz
"""


class FakeLLM:
    """System prompt'a göre sabit yanıt döndüren LLM taklidi."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.fail_all = False

    async def chat(self, system_prompt: str, user_prompt: str, *, temperature=None) -> str:
        from app.core.exceptions import LLMUnavailableError

        if self.fail_all:
            raise LLMUnavailableError()
        if "sınıflandırma uzmanı" in system_prompt:
            self.calls.append("classify")
            return json.dumps({"document_type": "Dilekçe", "confidence": 0.92, "sub_type": None,
                               "reasoning": "Vatandaş talebi içeriyor."})
        if "analiz uzmanı" in system_prompt:
            self.calls.append("analyze")
            return "```json\n" + json.dumps({
                "entities": [{"entity_type": "kisi", "value": "Ayşe Yılmaz"}, {"bozuk": True}],
                "missing_fields": [{"field_name": "sayi", "description": "Sayı yok", "is_critical": True}],
                "keywords": ["kaldırım", "onarım"],
            }) + "\n```"
        if "mevzuat uzmanı" in system_prompt:
            self.calls.append("legislation")
            return json.dumps({"matches": [
                {"legislation_name": "3071 sayılı Dilekçe Hakkı Kanunu", "article": 7, "relevance_score": 0.9, "summary": "Dilekçe süresi"},
            ]})
        if "özetleme uzmanı" in system_prompt:
            self.calls.append("summary")
            return "Vatandaş kaldırım onarımı talep etmektedir."
        if "yazışma uzmanı" in system_prompt:
            self.calls.append("draft")
            return json.dumps({"draft_type": "ust_yazi", "subject": "Kaldırım onarımı", "body": "Talebiniz incelenmiştir.",
                               "formal_greeting": "Sayın Ayşe Yılmaz", "closing": "Bilgilerinize rica ederim.",
                               "attachments_note": "null", "tone_check": "Uygun"})
        if "yönlendirme uzmanı" in system_prompt:
            self.calls.append("routing")
            return json.dumps({"target_unit": "fen işleri", "reasoning": "Altyapı talebi", "priority": "Yüksek",
                               "alternative_units": [], "requires_action": ["Yerinde inceleme"]})
        if "karşılaştırma uzmanı" in system_prompt:
            self.calls.append("compare")
            return json.dumps({"similarity_score": 1.4, "common_themes": ["talep"], "differences": [],
                               "text1_unique": "", "text2_unique": "", "recommendation": "Benzer"})
        raise AssertionError(f"Beklenmeyen prompt: {system_prompt[:60]}")


@pytest.fixture()
def fake_llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture()
def client(tmp_path, fake_llm):
    settings = Settings(
        _env_file=None,
        HISTORY_DIR=str(tmp_path / "history"),
        UPLOAD_DIR=str(tmp_path / "uploads"),
        RAG_INDEX_DIR=str(tmp_path / "rag"),
        LLM_API_KEY="test",
    )
    app = create_app(settings)
    with TestClient(app) as test_client:
        app.state.container.llm.chat = fake_llm.chat
        yield test_client
