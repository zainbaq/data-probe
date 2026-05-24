import logging
import time
import uuid

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from app.config import settings
from app.database import AsyncSessionLocal, engine
from app.logging import configure_logging
from app.rate_limiter import limiter

configure_logging()
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
    )

    # Rate limiting
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next) -> Response:
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = int((time.perf_counter() - start) * 1000)
        response.headers["x-request-id"] = request_id
        response.headers["x-response-time"] = str(duration_ms)
        return response

    @app.get("/health", tags=["ops"])
    async def health() -> dict:
        checks: dict[str, str] = {}

        try:
            async with AsyncSessionLocal() as session:
                await session.execute(text("SELECT 1"))
            checks["database"] = "ok"
        except Exception as e:
            logger.error("DB health check failed: %s", e)
            checks["database"] = "error"

        try:
            import redis.asyncio as aioredis
            r = aioredis.from_url(settings.redis_url, socket_connect_timeout=2)
            await r.ping()
            await r.aclose()
            checks["redis"] = "ok"
        except Exception as e:
            logger.error("Redis health check failed: %s", e)
            checks["redis"] = "error"

        overall = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
        return {"status": overall, "checks": checks}

    # Register API routers
    from app.api.v1.router import router as v1_router
    app.include_router(v1_router, prefix=settings.api_v1_prefix)

    @app.on_event("startup")
    async def startup_validation():
        if not settings.encryption_key:
            raise RuntimeError("ENCRYPTION_KEY must be set")
        if not settings.clerk_webhook_secret:
            logger.warning("CLERK_WEBHOOK_SECRET not set — webhook auth disabled")
        if not settings.anthropic_api_key:
            logger.warning("ANTHROPIC_API_KEY not set — LLM analysis will fail")

    return app


app = create_app()
