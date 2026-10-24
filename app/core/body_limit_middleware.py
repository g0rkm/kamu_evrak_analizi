from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

class BodyLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_body_bytes: int = 104857600):
        super().__init__(app)
        self.max_body_bytes = max_body_bytes

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_body_bytes:
            max_mb = self.max_body_bytes / (1024 * 1024)
            return JSONResponse(
                status_code=413,
                content={"detail": f"Istek boyutu siniri asildi. Maksimum: {max_mb:.0f} MB"}
            )
        return await call_next(request)
