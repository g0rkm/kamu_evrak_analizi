from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
import time
import threading

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_requests: int = 60, window: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window = window
        self.requests = {}
        self.lock = threading.Lock()

    async def dispatch(self, request: Request, call_next):
        # Sağlık kontrol uç noktalarını rate limit'den muaf tut
        if request.url.path in ("/api/health", "/api/ready"):
            response = await call_next(request)
            return response

        client_ip = request.client.host if request.client else "unknown"
        current_time = time.time()

        with self.lock:
            if client_ip not in self.requests:
                self.requests[client_ip] = []

            # Zaman penceresi dışındaki istekleri temizle
            self.requests[client_ip] = [
                req_time for req_time in self.requests[client_ip]
                if current_time - req_time < self.window
            ]

            if len(self.requests[client_ip]) >= self.max_requests:
                return JSONResponse(
                    status_code=429,
                    content={"error": "rate_limit_exceeded", "message": "Çok fazla istek gönderildi. Lütfen daha sonra tekrar deneyin."}
                )

            self.requests[client_ip].append(current_time)

        response = await call_next(request)
        return response
