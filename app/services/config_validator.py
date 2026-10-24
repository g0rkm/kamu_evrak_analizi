from pathlib import Path

class ConfigValidator:
    def __init__(self):
        self._warnings = []
        self._errors = []
    
    def validate(self, settings) -> dict:
        self._warnings = []
        self._errors = []
        self._check_api_key(settings)
        self._check_directories(settings)
        self._check_limits(settings)
        self._check_security(settings)
        return {
            "valid": len(self._errors) == 0,
            "errors": self._errors,
            "warnings": self._warnings
        }
    
    def _check_api_key(self, settings):
        api_key = getattr(settings, 'LLM_API_KEY', '')
        if not api_key or api_key in ('your-gemini-api-key-here', 'test', ''):
            self._warnings.append("LLM_API_KEY ayarlanmamis veya gecersiz - analiz ozelligi calismaayacak")
    
    def _check_directories(self, settings):
        dirs_to_check = [
            ('HISTORY_DIR', getattr(settings, 'HISTORY_DIR', 'data/history')),
        ]
        for name, dir_path in dirs_to_check:
            p = Path(str(dir_path))
            if not p.exists():
                try:
                    p.mkdir(parents=True, exist_ok=True)
                    self._warnings.append(f"{name} dizini olusturuldu: {p}")
                except OSError as e:
                    self._errors.append(f"{name} dizini olusturulamadi: {e}")
    
    def _check_limits(self, settings):
        max_file = getattr(settings, 'MAX_FILE_SIZE_MB', 50)
        if max_file > 200:
            self._warnings.append(f"MAX_FILE_SIZE_MB cok yuksek: {max_file}MB")
        body_limit = getattr(settings, 'REQUEST_BODY_LIMIT_MB', 100)
        if body_limit > 500:
            self._warnings.append(f"REQUEST_BODY_LIMIT_MB cok yuksek: {body_limit}MB")
        if max_file > body_limit:
            self._errors.append(f"MAX_FILE_SIZE_MB ({max_file}) REQUEST_BODY_LIMIT_MB ({body_limit}) degerinden buyuk olamaz")
    
    def _check_security(self, settings):
        env = getattr(settings, 'ENVIRONMENT', 'development')
        cors = getattr(settings, 'CORS_ORIGINS', '*')
        if env == 'production' and cors == '*':
            self._warnings.append("Production ortaminda CORS_ORIGINS='*' guvenlik riski olusturabilir")
        rate_limit = getattr(settings, 'RATE_LIMIT_PER_MINUTE', 60)
        if rate_limit > 1000:
            self._warnings.append(f"Rate limit cok yuksek: {rate_limit}/dk")
    
    def get_report(self) -> dict:
        return {
            "errors": self._errors,
            "warnings": self._warnings,
            "has_errors": len(self._errors) > 0,
            "has_warnings": len(self._warnings) > 0
        }
