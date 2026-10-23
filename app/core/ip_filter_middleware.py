from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.requests import Request
import ipaddress
import logging

logger = logging.getLogger(__name__)

class IPFilterMiddleware(BaseHTTPMiddleware):
    """IP whitelist ve blacklist middleware. Bos whitelist = herkese acik."""
    
    def __init__(self, app, whitelist: str = "", blacklist: str = ""):
        super().__init__(app)
        self.whitelist = self._parse_ips(whitelist)
        self.blacklist = self._parse_ips(blacklist)
    
    def _parse_ips(self, ip_string: str) -> set[str]:
        if not ip_string or not ip_string.strip():
            return set()
        ips = set()
        for part in ip_string.split(","):
            part = part.strip()
            if part:
                ips.add(part)
        return ips
    
    def _get_client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        if request.client:
            return request.client.host
        return "unknown"
    
    def _is_allowed(self, ip: str) -> bool:
        if ip in self.blacklist:
            return False
        if not self.whitelist:
            return True
        return ip in self.whitelist
    
    async def dispatch(self, request: Request, call_next):
        client_ip = self._get_client_ip(request)
        
        if not self._is_allowed(client_ip):
            logger.warning(f"IP engellendi: {client_ip} - {request.method} {request.url.path}")
            return JSONResponse(
                status_code=403,
                content={"detail": "Erisim engellendi", "ip": client_ip}
            )
        
        response = await call_next(request)
        return response
