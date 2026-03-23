import os
os.environ["ANONYMIZED_TELEMETRY"] = "false"
os.environ["CHROMA_TELEMETRY"] = "false"

from app.core.logging import setup_logging
setup_logging()

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.router import router
from app.core.config import get_settings
from app.core.exceptions import AppException
from app.middleware.rate_limit import limiter
from app.middleware.logging import RequestLoggingMiddleware
from app.middleware.error_handler import (
    app_exception_handler,
    validation_exception_handler,
    global_exception_handler,
)
from app.db.base import Base
from app.db.session import engine
from app.db.models.user import User          # noqa: F401
from app.db.models.interaction import InteractionLog  # noqa: F401

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs("data/chroma", exist_ok=True)
    os.makedirs("data", exist_ok=True)
    Base.metadata.create_all(bind=engine)

    from app.services.embedding import get_model, get_chroma_collection
    get_chroma_collection()
    get_model()

    logger.info({
        "event": "startup",
        "hf_model": settings.hf_model_name,
        "top_n": settings.top_n_results,
        "groq_enabled": bool(settings.groq_api_key),
        "cache_enabled": bool(settings.upstash_redis_rest_url),
    })
    yield
    logger.info({"event": "shutdown"})


app = FastAPI(
    title="Article Recommender API",
    description="Content-based article recommendation — JWT auth + Redis cache + Pinecone",
    version="1.0.0",
    lifespan=lifespan,
)

# Middleware — order matters: first added = last executed
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Error handlers
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)

app.include_router(router, prefix="/api/v1")


@app.get("/")
def root():
    return {
        "service": settings.app_name,
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/v1/health",
    }