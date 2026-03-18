import os
# Must be set before chromadb is imported anywhere
os.environ["ANONYMIZED_TELEMETRY"] = "false"
os.environ["CHROMA_TELEMETRY"] = "false"

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.router import router
from app.core.config import get_settings
from app.middleware.rate_limit import limiter

from app.db.base import Base
from app.db.session import engine
from app.db.models.user import User          # noqa: F401
from app.db.models.interaction import InteractionLog  # noqa: F401

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs("data/chroma", exist_ok=True)
    os.makedirs("data", exist_ok=True)

    Base.metadata.create_all(bind=engine)

    logger.info("DB tables ready")
    logger.info(f"HF model     : {settings.hf_model_name}")
    logger.info(f"Top-N results: {settings.top_n_results}")
    logger.info(f"Groq enabled : {bool(settings.groq_api_key)} (model: {settings.groq_model})")
    logger.info(f"Token expiry : {settings.access_token_expire_minutes} min")
    yield


app = FastAPI(
    title="Article Recommender API",
    description="Content-based article recommendation — JWT auth + rate limiting",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")


@app.get("/")
def root():
    return {
        "service": settings.app_name,
        "docs": "/docs",
        "health": "/api/v1/health",
    }