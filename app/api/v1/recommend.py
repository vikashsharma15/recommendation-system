from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
import logging

from app.db.session import get_db
from app.db.models import User
from app.schemas.recommend import RecommendResponse, ArticleOut, InteractionCreate
from app.middleware.auth import get_current_user
from app.middleware.rate_limit import limiter
from app.services.recommendation import recommend_for_user, log_interaction
from app.services.groq import get_groq_explanation

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("", response_model=RecommendResponse)
@limiter.limit("30/minute")
def get_recommendations(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get top-N article recommendations. Rate limited: 30/minute."""
    user, results = recommend_for_user(db, current_user.id)

    if not results:
        raise HTTPException(
            status_code=503,
            detail="No articles indexed yet. Run the ingest script first.",
        )

    articles = [ArticleOut(**r) for r in results]
    groq_summary = get_groq_explanation(current_user.interests, results)

    return RecommendResponse(
        user_id=current_user.id,
        username=current_user.username,
        recommendations=articles,
        groq_summary=groq_summary,
    )


@router.post("/interact", status_code=200)
@limiter.limit("60/minute")
def record_interaction(
    request: Request,
    payload: InteractionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Log article interaction: viewed | liked | skipped."""
    if payload.action not in {"viewed", "liked", "skipped"}:
        raise HTTPException(status_code=400, detail="action must be: viewed | liked | skipped")

    log_interaction(db, current_user.id, payload.article_id, payload.action)
    return {"message": f"'{payload.action}' logged for article {payload.article_id}"}