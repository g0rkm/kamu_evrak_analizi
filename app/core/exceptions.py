"""Uygulama hata hiyerarşisi.

Her hata, API katmanında kullanıcıya gösterilecek Türkçe mesajı, HTTP durum
kodunu ve istemcinin programatik olarak ayırt edebileceği bir `code` taşır.
"""


class AppError(Exception):
    status_code: int = 500
    code: str = "internal_error"
    default_message: "Beklenmeyen bir hata oluştu."

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.default_message
        super().__init__(self.message)


class InvalidInputError(AppError):
    status_code = 400
    code = "invalid_input"
    default_message = "Geçersiz girdi."


class UnsupportedFileTypeError(InvalidInputError):
    status_code = 415
    code = "unsupported_file_type"
    default_message = "Bu dosya türü desteklenmiyor."


class FileTooLargeError(InvalidInputError):
    status_code = 413
    code = "file_too_large"
    default_message = "Dosya boyutu izin verilen sınırı aşıyor."


class FileValidationError(AppError):
    status_code = 400
    code = "file_validation_error"
    default_message = "Dosya doğrulama hatası."


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"
    default_message = "Kayıt bulunamadı."


class TextExtractionError(AppError):
    status_code = 422
    code = "text_extraction_failed"
    default_message = "Evraktan okunabilir metin çıkarılamadı."


class LLMError(AppError):
    status_code = 502
    code = "llm_error"
    default_message = "Yapay zekâ servisi isteği işleyemedi."


class LLMAuthError(LLMError):
    code = "llm_auth_error"
    default_message = "Yapay zekâ servisi kimlik doğrulaması başarısız. API anahtarını kontrol edin."


class LLMUnavailableError(LLMError):
    status_code = 503
    code = "llm_unavailable"
    default_message = "Yapay zekâ servisine şu anda ulaşılamıyor. Lütfen biraz sonra tekrar deneyin."


class LLMResponseError(LLMError):
    code = "llm_bad_response"
    default_message = "Yapay zekâ servisi beklenen biçimde yanıt vermedi."


class PipelineTimeoutError(AppError):
    """Pipeline süre aşımı."""
    status_code = 504
    code = "pipeline_timeout"
    default_message = "Pipeline süresi aşıldı."


class CircuitBreakerOpenError(LLMUnavailableError):
    """Devre kesici açık — LLM servisi geçici olarak devre dışı."""
    code = "circuit_breaker_open"
    default_message = "Yapay zekâ servisi art arda hatalar nedeniyle geçici olarak devre dışı bırakıldı. Lütfen birkaç dakika sonra tekrar deneyin."


class RateLimitError(AppError):
    status_code = 429
    code = "rate_limit_exceeded"
    default_message = "İstek sınırı aşıldı. Lütfen biraz bekleyin."


class MaintenanceModeError(AppError):
    """Sistem bakım modundayken gelen istekler için."""
    status_code = 503
    code = "maintenance_mode"
    default_message = "Sistem şu anda bakım modundadır. Lütfen daha sonra tekrar deneyin."


class TokenBudgetExceededError(AppError):
    status_code = 429
    code = 'token_budget_exceeded'
    default_message = 'Token bütçesi aşıldı. Lütfen daha sonra tekrar deneyin.'


class ConfigurationError(AppError):
    status_code = 500
    code = "configuration_error"
    default_message = "Yapılandırma hatası oluştu."
