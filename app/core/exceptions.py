"""Uygulama hata hiyerarşisi.

Her hata, API katmanında kullanıcıya gösterilecek Türkçe mesajı, HTTP durum
kodunu ve istemcinin programatik olarak ayırt edebileceği bir `code` taşır.
"""


class AppError(Exception):
    status_code: int = 500
    code: str = "internal_error"
    default_message: str = "Beklenmeyen bir hata oluştu."

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
