import httpx
import json
import re
from app.config import get_settings

class LLMService:
    """OpenAI-uyumlu LLM API servisi."""
    
    def __init__(self):
        settings = get_settings()
        self.api_base = settings.LLM_API_BASE
        self.api_key = settings.LLM_API_KEY
        self.model = settings.LLM_MODEL
        self.client = httpx.AsyncClient(timeout=120.0)
    
    async def chat(self, system_prompt: str, user_prompt: str) -> str:
        """Tek bir chat completion isteği gönder, yanıt metnini döndür."""
        url = f"{self.api_base}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.3
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        response = await self.client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
    
    async def chat_json(self, system_prompt: str, user_prompt: str) -> dict:
        """Chat completion isteği gönder, yanıtı JSON olarak parse et.
        LLM bazen markdown code fence içinde JSON döndürür, bunu temizle."""
        raw = await self.chat(system_prompt, user_prompt)
        # Markdown code fence temizliği
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            # ```json veya ``` ile başlayan bloğu temizle
            lines = cleaned.split("\n")
            # İlk ve son ``` satırlarını kaldır
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines)
        return json.loads(cleaned)
    
    async def close(self):
        await self.client.aclose()
