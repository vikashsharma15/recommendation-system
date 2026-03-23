"""
GET  /api/v1/recommend          — Paginated recommendations
POST /api/v1/recommend/interact — Log interaction
GET  /api/v1/recommend/cache/status — Debug

Performance:
- Redis cache: 5 min TTL, HIT < 200ms
- Cache MISS: Pinecone search ~2-4s (cold), ~500ms (warm)
- X-Cache header: HIT/MISS for debugging
"""
from fastapi import APIRouter, Depends, Request, Query, Response
from sqlalchemy.orm import Session
import logging

from app.db.session import get_db
from app.db.models.user import User
from app.db.models.interaction import InteractionLog
from app.schemas.recommend import RecommendResponse, ArticleOut, InteractionCreate
from app.schemas.common import ApiResponse, Meta
from app.middleware.auth import get_current_user
from app.middleware.rate_limit import limiter
from app.services.recommendation import recommend_for_user, log_interaction
from app.services.groq import get_groq_explanation
from app.services import cache
from app.core.config import get_settings
from app.core.exceptions import NoArticlesIndexedError

logger   = logging.getLogger(__name__)
router   = APIRouter()
settings = get_settings()


def _req_id(request: Request) -> str:
    return getattr(request.state, "request_id", None)


@router.get("", response_model=ApiResponse[RecommendResponse])
@limiter.limit("30/minute")
def get_recommendations(
    request:      Request,
    response:     Response,
    page:         int = Query(default=1, ge=1),
    page_size:    int = Query(default=None),
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    effective_size = min(page_size or settings.default_page_size, settings.max_page_size)

    cache_key = cache.make_recommend_key(current_user.id)
    cache_hit  = cache.exists(cache_key)

    user, results = recommend_for_user(db, current_user.id)
    if not results:
        raise NoArticlesIndexedError()

    # Pagination
    total = len(results)
    start = (page - 1) * effective_size
    end   = start + effective_size
    paginated = results[start:end]

    # Groq — page 1 only
    groq_summary = None
    if page == 1:
        groq_summary = get_groq_explanation(
            user_id=current_user.id,
            user_interests=current_user.interests or [],
            articles=paginated,
        )

    response.headers["X-Cache"]      = "HIT" if cache_hit else "MISS"
    response.headers["X-Request-ID"] = _req_id(request) or ""
    response.headers["X-Total"]      = str(total)

    return ApiResponse(
        message="Recommendations fetched successfully",
        data=RecommendResponse(
            user_id=current_user.id,
            username=current_user.username,
            recommendations=[ArticleOut(**r) for r in paginated],
            groq_summary=groq_summary,
        ),
        meta=Meta(
            page=page,
            page_size=effective_size,
            total=total,
        ),
        request_id=_req_id(request),
    )


@router.post("/interact", response_model=ApiResponse, status_code=200)
@limiter.limit("60/minute")
def record_interaction(
    request:      Request,
    payload:      InteractionCreate,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    # Idempotency check
    existing = db.query(InteractionLog).filter(
        InteractionLog.user_id    == current_user.id,
        InteractionLog.article_id == payload.article_id,
        InteractionLog.action     == payload.action.value,
    ).first()

    if existing:
        return ApiResponse(message="Already recorded", request_id=_req_id(request))

    log_interaction(db, current_user.id, payload.article_id, payload.action.value)
    return ApiResponse(message="Interaction logged", request_id=_req_id(request))


@router.get("/cache/status", response_model=ApiResponse)
@limiter.limit("10/minute")
def cache_status(
    request:      Request,
    current_user: User = Depends(get_current_user),
):
    rec_key  = cache.make_recommend_key(current_user.id)
    groq_key = cache.make_groq_key(current_user.id)
    return ApiResponse(
        message="Cache status",
        data={
            "recommend":   {"cached": cache.exists(rec_key),  "ttl": cache.get_ttl(rec_key)},
            "groq_summary":{"cached": cache.exists(groq_key), "ttl": cache.get_ttl(groq_key)},
            "backend":     cache.ping(),
        },
        request_id=_req_id(request),
    )