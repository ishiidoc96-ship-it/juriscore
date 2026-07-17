import os
import logging
import sys
import uuid
import time
from contextlib import asynccontextmanager
from typing import Optional

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from prometheus_fastapi_instrumentator import Instrumentator
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor

from api.backend.models.database import engine, Base, async_session
from sqlalchemy import text
from api.backend.middleware.auth import SupabaseAuthMiddleware
from api.backend.middleware.security import (
    SecurityHeadersMiddleware,
    RateLimitMiddleware,
    InputValidationMiddleware,
)
from api.backend.services import ai_service
from api.backend.services.local_db import is_ready as local_db_ready
from api.backend.routers import (
    cases,
    statutes,
    constitution,
    notebook,
    flashcards,
    study,
    export,
    search,
    bookmarks,
    gazettes,
    tribunals,
    auth,
    workspaces,
    history,
    student_workspace,
)

load_dotenv()

# ── Structured Logging Setup ─────────────────────────────────────────────────

def configure_structlog():
    """Configure structlog with JSON output and request ID correlation."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging to use structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO,
    )

    # Capture stdlib logs via structlog
    LoggingInstrumentor().instrument(set_logging_format=True)


configure_structlog()
logger = structlog.get_logger(__name__)


# ── OpenTelemetry Tracing Setup ──────────────────────────────────────────────

def configure_tracing():
    """Configure OpenTelemetry tracing with OTLP exporter."""
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not otlp_endpoint:
        logger.info("OTEL_EXPORTER_OTLP_ENDPOINT not set, skipping tracing setup")
        return

    provider = TracerProvider()
    trace.set_tracer_provider(provider)

    exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(exporter))

    # Instrument FastAPI, SQLAlchemy, HTTPX, and logging
    FastAPIInstrumentor.instrument()
    SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)
    HTTPXClientInstrumentor().instrument()
    LoggingInstrumentor().instrument(set_logging_format=True)

    logger.info("OpenTelemetry tracing configured", endpoint=otlp_endpoint)


# ── Prometheus Metrics Setup ─────────────────────────────────────────────────

def configure_metrics(app: FastAPI):
    """Configure Prometheus metrics with custom metrics."""
    instrumentator = Instrumentator(
        should_group_status_codes=False,
        should_ignore_untemplated=True,
        should_respect_env_var=True,
        should_instrument_requests_inprogress=True,
        excluded_handlers=["/health", "/ready", "/metrics"],
        env_var_name="ENABLE_METRICS",
    )

    # Add custom metrics
    from prometheus_client import Counter, Histogram, Gauge

    # Custom metrics
    search_latency = Histogram(
        "juriscore_search_latency_seconds",
        "Search request latency in seconds",
        buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
    )
    ai_latency = Histogram(
        "juriscore_ai_latency_seconds",
        "AI service latency in seconds",
        buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
    )
    cache_hits = Counter(
        "juriscore_cache_hits_total",
        "Total cache hits",
        ["cache_type"],
    )
    cache_misses = Counter(
        "juriscore_cache_misses_total",
        "Total cache misses",
        ["cache_type"],
    )
    rate_limit_hits = Counter(
        "juriscore_rate_limit_hits_total",
        "Total rate limit hits",
        ["endpoint"],
    )
    active_requests = Gauge(
        "juriscore_active_requests",
        "Number of currently active requests",
    )

    # Store custom metrics on app state for use in routes
    app.state.metrics = {
        "search_latency": search_latency,
        "ai_latency": ai_latency,
        "cache_hits": cache_hits,
        "cache_misses": cache_misses,
        "rate_limit_hits": rate_limit_hits,
        "active_requests": active_requests,
    }

    instrumentator.instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
    logger.info("Prometheus metrics configured")


# ── Request ID Middleware ────────────────────────────────────────────────────


async def request_id_middleware(request: Request, call_next):
    """Add request ID to all requests and log structured request/response info."""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id

    # Bind request ID to structlog context
    structlog.contextvars.bind_contextvars(request_id=request_id)

    start_time = time.perf_counter()

    # Increment active requests gauge
    if hasattr(request.app.state, "metrics"):
        request.app.state.metrics["active_requests"].inc()

    try:
        response = await call_next(request)
    except Exception as e:
        logger.exception("Request failed", error=str(e))
        raise
    finally:
        duration_ms = (time.perf_counter() - start_time) * 1000
        if hasattr(request.app.state, "metrics"):
            request.app.state.metrics["active_requests"].dec()

        logger.info(
            "Request completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code if 'response' in locals() else 500,
            duration_ms=round(duration_ms, 2),
        )

    response.headers["X-Request-ID"] = request_id
    return response


# ── Global Exception Handler ─────────────────────────────────────────────────


async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler with structured error responses."""
    request_id = getattr(request.state, "request_id", "unknown")

    logger.exception(
        "Unhandled exception",
        request_id=request_id,
        path=request.url.path,
        method=request.method,
        error_type=type(exc).__name__,
        error_message=str(exc),
    )

    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": "An unexpected error occurred",
            "request_id": request_id,
        },
    )


# ── Health & Readiness Checks ────────────────────────────────────────────────


async def check_db_connection() -> bool:
    """Check database connectivity."""
    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.warning("Database health check failed", error=str(e))
        return False


async def check_redis_connection() -> bool:
    """Check Redis connectivity."""
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        return True  # Redis not configured, skip check
    try:
        import redis.asyncio as redis
        client = redis.from_url(redis_url)
        await client.ping()
        await client.close()
        return True
    except Exception as e:
        logger.warning("Redis health check failed", error=str(e))
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan with observability setup."""
    logger.info("Starting Juriscore API...")

    # Configure tracing
    try:
        configure_tracing()
    except Exception as e:
        logger.warning("Tracing setup failed, continuing without tracing", error=str(e))

    # Create database tables
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created")
    except Exception as e:
        logger.warning("Database table creation failed", error=str(e))

    # Initialize AI service
    try:
        ai_service.init_backend()
        logger.info("AI service initialized")
    except Exception as e:
        logger.warning("AI service init failed", error=str(e))

    # Load local DB (brain)
    try:
        local_db_ready()
        logger.info("Local database loaded")
    except Exception as e:
        logger.warning("Local database not loaded", error=str(e))

    logger.info("Juriscore API ready")
    yield

    logger.info("Shutting down Juriscore API")


# ── FastAPI App Creation ─────────────────────────────────────────────────────

app = FastAPI(
    title="Juriscore API",
    description="Legal research companion for Kenyan law students.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc",
    openapi_url="/api/v1/openapi.json",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth middleware
app.add_middleware(SupabaseAuthMiddleware)

# Security middlewares
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(InputValidationMiddleware)
app.add_middleware(RateLimitMiddleware, requests_per_minute=int(os.getenv("RATE_LIMIT_PER_MINUTE", "100")))

# Add middlewares
app.middleware("http")(request_id_middleware)
app.add_exception_handler(Exception, global_exception_handler)

# Configure metrics after app creation
configure_metrics(app)


# ── Health & Readiness Endpoints ─────────────────────────────────────────────


@app.get("/health", tags=["Health"])
async def health():
    """Liveness probe - always returns 200 if process is alive."""
    from api.backend.services import ai_service

    ai_configured = ai_service._is_configured()

    return {
        "status": "healthy",
        "service": "juriscore-api",
        "version": "1.0.0",
        "features": {
            "ai_enabled": ai_configured,
            "ai_fast_provider": ai_service._provider.value if ai_service._provider else None,
            "ai_reasoning_provider": ai_service._reasoning_provider.value if ai_service._reasoning_provider else None,
        }
    }


@app.get("/ready", tags=["Health"])
async def ready():
    """Readiness probe - checks dependencies."""
    from api.backend.services import ai_service
    
    db_ok = await check_db_connection()
    redis_ok = await check_redis_connection()
    brain_ok = local_db_ready()
    ai_ok = ai_service._is_configured()

    ready = db_ok and redis_ok and brain_ok

    return JSONResponse(
        status_code=200 if ready else 503,
        content={
            "ready": ready,
            "checks": {
                "database": db_ok,
                "redis": redis_ok,
                "brain_data": brain_ok,
                "ai_service": ai_ok,
            },
            "service": "juriscore-api",
            "version": "1.0.0",
            "warnings": [
                "AI features disabled - no API key configured" if not ai_ok else None
            ] if not ai_ok else []
        },
    )


@app.get("/", tags=["Root"])
async def root():
    return JSONResponse({"message": "Welcome to Juriscore API", "docs": "/api/v1/docs"})


# ── Router Registration ──────────────────────────────────────────────────────

API_PREFIX = "/api/v1"

app.include_router(cases.router, prefix=f"{API_PREFIX}/cases", tags=["Cases"])
app.include_router(statutes.router, prefix=f"{API_PREFIX}/statutes", tags=["Statutes"])
app.include_router(constitution.router, prefix=f"{API_PREFIX}/constitution", tags=["Constitution"])
app.include_router(notebook.router, prefix=f"{API_PREFIX}/notebook", tags=["Notebook"])
app.include_router(flashcards.router, prefix=f"{API_PREFIX}/flashcards", tags=["Flashcards"])
app.include_router(study.router, prefix=f"{API_PREFIX}/study", tags=["Study"])
app.include_router(export.router, prefix=f"{API_PREFIX}/export", tags=["Export"])
app.include_router(search.router, prefix=f"{API_PREFIX}/search", tags=["Search"])
app.include_router(bookmarks.router, prefix=f"{API_PREFIX}/bookmarks", tags=["Bookmarks"])
app.include_router(gazettes.router, prefix=f"{API_PREFIX}/gazettes", tags=["Gazettes"])
app.include_router(tribunals.router, prefix=f"{API_PREFIX}/tribunals", tags=["Tribunals"])
app.include_router(auth.router, prefix=f"{API_PREFIX}/auth", tags=["Auth"])
app.include_router(workspaces.router, prefix=f"{API_PREFIX}/workspaces", tags=["Workspaces"])
app.include_router(history.router, prefix=f"{API_PREFIX}/history", tags=["History"])
app.include_router(student_workspace.router, prefix=f"{API_PREFIX}/student", tags=["Student Workspace"])