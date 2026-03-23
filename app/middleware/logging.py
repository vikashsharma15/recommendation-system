import uuid
import time
import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Assigns unique request_id to every request.
    Logs method, path, status, duration.
    Attaches request_id to request state — available in all routes.
    """

    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id

        start = time.perf_counter()

        response = await call_next(request)

        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        logger.info({
            "request_id": request_id,
            "method": request.method,
            "path": str(request.url.path),
            "status": response.status_code,
            "duration_ms": duration_ms,
        })

        response.headers["X-Request-ID"] = request_id
        return response