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
        LLM bazen markdown code fence içinde veya ekstra metinle JSON döndürür."""
        raw = await self.chat(system_prompt, user_prompt)
        cleaned = raw.strip()
        
        # Markdown code fence temizliği
        if "```" in cleaned:
            # Code fence bloğunun içeriğini çıkar
            fence_pattern = re.compile(r'```(?:json)?\s*\n?(.*?)\n?\s*```', re.DOTALL)
            match = fence_pattern.search(cleaned)
            if match:
                cleaned = match.group(1).strip()
        
        # JSON objesini bulmaya çalış (ilk { ile son } arası)
        if not cleaned.startswith("{") and not cleaned.startswith("["):
            # Metin içinde JSON objesini ara
            start_brace = cleaned.find("{")
            start_bracket = cleaned.find("[")
            
            if start_brace == -1 and start_bracket == -1:
                raise ValueError(f"JSON bulunamadı. LLM yanıtı: {raw[:500]}")
            
            # Hangisi önce geliyorsa onu kullan
            if start_bracket == -1 or (start_brace != -1 and start_brace < start_bracket):
                start = start_brace
                end = cleaned.rfind("}") + 1
            else:
                start = start_bracket
                end = cleaned.rfind("]") + 1
            
            if end <= start:
                raise ValueError(f"Geçersiz JSON yapısı. LLM yanıtı: {raw[:500]}")
            
            cleaned = cleaned[start:end]
        
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON parse hatası: {e}. Temizlenmiş metin: {cleaned[:500]}")
    
    async def close(self):
        await self.client.aclose()
