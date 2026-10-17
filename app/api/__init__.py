from .routes import router

TAGS_METADATA = [
    {"name": "analiz", "description": "Evrak analizi ve karşılaştırma işlemleri"},
    {"name": "geçmiş", "description": "Analiz geçmişi yönetimi"},
    {"name": "sistem", "description": "Sağlık kontrolleri ve sistem bilgileri"},
]

__all__ = ["router", "TAGS_METADATA"]
