"""
GET  /api/v1/recommend          — Paginated recommendations
POST /api/v1/recommend/interact — Log interaction
GET  /api/v1/recommend/cache/status — Debug

Performance targets:
  Cache HIT  (Redis)   → < 50ms  end-to-end
  Cache HIT  (memory)  → < 10ms  end-to-end
  Cache MISS (cold)    → ~500ms–1s  (Pinecone + Groq cached separately)
  X-Cache header       → HIT / MISS
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
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
    return getattr(request.state, "request_id", "") or ""


# ── GET /recommend ─────────────────────────────────────────

@router.get("", response_model=ApiResponse[RecommendResponse])
@limiter.limit("30/minute")
def get_recommendations(
    request:   Request,
    response:  Response,
    page:      int = Query(default=1, ge=1),
    page_size: int = Query(default=None, ge=1),   # ge=1 guards div-by-zero
    db:        Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Edge cases handled:
      ✓ Cache HIT  → skip Pinecone, skip Groq (< 50ms)
      ✓ Cache MISS → fetch Pinecone, cache results, then paginate
      ✓ Groq cache → separate key, separate TTL (10 min)
      ✓ Groq error → log + continue (summary = None, don't fail the request)
      ✓ Empty index → 404 NoArticlesIndexedError
      ✓ page beyond total → 400 with clear message
      ✓ page_size=0 → rejected by Query(ge=1)
      ✓ Redis down → in-memory fallback transparent to caller
    """
    effective_size = min(
        page_size or settings.default_page_size,
        settings.max_page_size,
    )

    rec_key = cache.make_recommend_key(current_user.id)

    # ── ONE round-trip: check + read in a single cache.get() ──────────────
    # BUG FIX: original code called cache.exists() (read nothing) then always
    # called recommend_for_user() — cache was cosmetic, not functional.
    results   = cache.get(rec_key)
    cache_hit = results is not None

    if not cache_hit:
        # Cold path: Pinecone search (~200ms–1s)
        _user, results = recommend_for_user(db, current_user.id)
        if not results:
            raise NoArticlesIndexedError()
        # Store full result list; pagination is done in-memory below.
        # TTL from settings (default 5 min).
        cache.set(rec_key, results)

    # ── Pagination ─────────────────────────────────────────────────────────
    total = len(results)
    start = (page - 1) * effective_size

    if start >= total and total > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Page out of range",
                "page": page,
                "total_items": total,
                "last_page": max(1, -(-total // effective_size)),  # ceil division
            },
        )

    paginated = results[start : start + effective_size]

    # ── Groq summary — page 1 only, with its own cache ────────────────────
    groq_summary = None
    if page == 1:
        groq_key     = cache.make_groq_key(current_user.id)
        groq_summary = cache.get(groq_key)

        if groq_summary is None:
            try:
                groq_summary = get_groq_explanation(
                    user_id=current_user.id,
                    user_interests=current_user.interests or [],
                    articles=paginated,
                )
                if groq_summary:
                    groq_ttl = getattr(settings, "cache_groq_ttl_seconds", 600)
                    cache.set(groq_key, groq_summary, ttl=groq_ttl)
            except Exception as exc:
                # Groq failure must not kill the whole request.
                # Frontend shows recommendations without summary.
                logger.warning(
                    "Groq explanation failed user_id=%s: %s",
                    current_user.id, exc,
                )

    # ── Response headers ───────────────────────────────────────────────────
    response.headers["X-Cache"]      = "HIT" if cache_hit else "MISS"
    response.headers["X-Request-ID"] = _req_id(request)
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


# ── POST /recommend/interact ───────────────────────────────

@router.post("/interact", response_model=ApiResponse, status_code=200)
@limiter.limit("60/minute")
def record_interaction(
    request:  Request,
    payload:  InteractionCreate,
    db:       Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Edge cases handled:
      ✓ Duplicate interaction → idempotent 200, no second write
      ✓ Invalid action value  → Pydantic rejects before we reach here
      ✓ DB error              → propagates as 500 (let global handler deal)
    """
    existing = (
        db.query(InteractionLog)
        .filter(
            InteractionLog.user_id    == current_user.id,
            InteractionLog.article_id == payload.article_id,
            InteractionLog.action     == payload.action.value,
        )
        .first()
    )

    if existing:
        return ApiResponse(
            message="Already recorded",
            request_id=_req_id(request),
        )

    log_interaction(db, current_user.id, payload.article_id, payload.action.value)
    return ApiResponse(
        message="Interaction logged",
        request_id=_req_id(request),
    )


# ── GET /recommend/cache/status ────────────────────────────

@router.get("/cache/status", response_model=ApiResponse)
@limiter.limit("10/minute")
def cache_status(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """
    Debug endpoint — shows TTL, hit/miss state, and Redis backend health.
    Intentionally not rate-limited hard; 10/min is enough for debugging.
    """
    rec_key  = cache.make_recommend_key(current_user.id)
    groq_key = cache.make_groq_key(current_user.id)

    return ApiResponse(
        message="Cache status",
        data={
            "recommend":    {"cached": cache.exists(rec_key),  "ttl": cache.get_ttl(rec_key)},
            "groq_summary": {"cached": cache.exists(groq_key), "ttl": cache.get_ttl(groq_key)},
            "backend":      cache.ping(),
        },
        request_id=_req_id(request),
    )