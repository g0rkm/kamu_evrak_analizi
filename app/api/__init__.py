from .routes import router

TAGS_METADATA = [
    {"name": "analiz", "description": "Evrak analizi ve karşılaştırma işlemleri"},
    {"name": "geçmiş", "description": "Analiz geçmişi yönetimi"},
    {"name": "sistem", "description": "Sağlık kontrolleri ve sistem bilgileri"},
    {"name": "Gecmis", "description": "Geçmiş kayıt işlemleri"},
    {"name": "Analiz", "description": "Analiz ve dosya işlemleri"},
    {"name": "Sistem", "description": "Sistem durumu ve yönetimi"},
    {"name": "Yetkilendirme", "description": "Kullanıcı kimlik doğrulama ve yetkilendirme"},
]

__all__ = ["router", "TAGS_METADATA"]
