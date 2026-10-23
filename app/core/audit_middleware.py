from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
import time, logging

logger = logging.getLogger(__name__)

SENSITIVE_PATHS = {
    "/api/auth/login", "/api/auth/register", "/api/auth/users",
    "/api/migration/run", "/api/cache/clear", "/api/system/cache-clear",
    "/api/sessions/cleanup", "/api/backup",
}

class AuditMiddleware(BaseHTTPMiddleware):
    """Hassas endpoint'lere yapilan istekleri denetim gunlugune kaydeder."""
    
    def __init__(self, app, audit_service=None):
        super().__init__(app)
        self.audit_service = audit_service
    
    def _get_client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        if request.client:
            return request.client.host
        return "unknown"
    
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        method = request.method
        start = time.time()
        
        response = await call_next(request)
        
        duration_ms = round((time.time() - start) * 1000, 1)
        
        if path in SENSITIVE_PATHS or (method in ("POST", "PUT", "DELETE") and "/api/" in path):
            client_ip = self._get_client_ip(request)
            log_entry = {
                "action": f"{method} {path}",
                "ip": client_ip,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "user_agent": request.headers.get("user-agent", "unknown"),
            }
            
            if self.audit_service:
                try:
                    self.audit_service.log(
                        action=f"api_access:{method}:{path}",
                        details=log_entry,
                        user="system"
                    )
                except Exception:
                    pass
            
            if path in SENSITIVE_PATHS:
                logger.info(f"AUDIT: {method} {path} -> {response.status_code} ({duration_ms}ms) ip={client_ip}")
        
        return response
