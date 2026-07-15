"""Request-level middleware for Juriscore.

Adds to every request:
- A unique X-Request-ID header (propagated from inbound or generated).
- Structured request logging via context-local request-id.
- Lightweight timing so downstream handlers can log latency without
  adding stopwatches per endpoint.
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

logger = logging.getLogger("juriscore.middleware")


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Attach a unique request ID to every incoming request.

    Reads ``X-Request-ID`` from the inbound request if present (propagation
    through reverse proxies / load balancers) or generates a fresh UUIDv4.

    The ID is set on:
    - ``request.state.request_id`` — for use inside handlers / deps
    - response header ``X-Request-ID`` — for client correlation
    - log record attribute ``request_id`` — set by ``_RequestIdFilter``
    """

    HEADER = "X-Request-ID"

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        incoming = request.headers.get(self.HEADER)
        req_id = incoming.strip() if incoming else str(uuid.uuid4())
        request.state.request_id = req_id

        # Make the request-id available to logging filters.
        # We use the standard `contextvars` pattern via the request state.
        import contextvars
        _REQUEST_ID_CTX.set(req_id)  # type: ignore[attr-defined]

        t0 = time.perf_counter()
        try:
            response: Response = await call_next(request)
        except Exception:
            elapsed = time.perf_counter() - t0
            logger.exception(
                "Unhandled exception (request_id=%s, %.1fms)", req_id, elapsed * 1000
            )
            raise

        elapsed = time.perf_counter() - t0
        logger.info(
            "%s %s %s %d %s %.1fms",
            request.method,
            request.url.path,
            response.status_code,
            elapsed * 1000,
            req_id[:8],
        )
        response.headers[self.HEADER] = req_id
        return response


# Context variable for the request-id (populated by the middleware above).
_REQUEST_ID_CTX: Any = None  # populated at first dispatch; see below


class _RequestIdLoggingFilter(logging.Filter):
    """Attach the current request-id to every log record emitted inside a
    request handler.  Noop outside a request context."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        try:
            import contextvars
            rid = _REQUEST_ID_CTX.get()  # type: ignore[union-attr]
        except (LookupError, AttributeError):
            rid = "-"
        record.request_id = rid  # type: ignore[attr-defined]
        return True
