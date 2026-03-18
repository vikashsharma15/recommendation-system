import logging
from typing import List, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.user import User
from app.db.models.interaction import InteractionLog
from app.services.embedding import search_similar

logger = logging.getLogger(__name__)
settings = get_settings()


def _build_query(user: User) -> str:
    interests = user.interests or []
    return " ".join(interests) if interests else "general news"


def _get_viewed_ids(db: Session, user_id: int) -> List[str]:
    logs = (
        db.query(InteractionLog)
        .filter(
            InteractionLog.user_id == user_id,
            InteractionLog.action.in_(["viewed", "liked"]),
        )
        .all()
    )
    return [log.article_id for log in logs]


def recommend_for_user(
    db: Session, user_id: int
) -> Tuple[Optional[User], Optional[List[Dict]]]:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None, None

    query_text = _build_query(user)
    logger.info(f"Recommending for user={user.username}, query='{query_text}'")

    results = search_similar(
        query_text=query_text,
        top_n=settings.top_n_results,
        exclude_ids=_get_viewed_ids(db, user_id),
    )
    return user, results


def log_interaction(db: Session, user_id: int, article_id: str, action: str) -> None:
    db.add(InteractionLog(user_id=user_id, article_id=article_id, action=action))
    db.commit()