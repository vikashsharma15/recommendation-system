import logging
from typing import List, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.user import User
from app.db.models.interaction import InteractionLog
from app.services.embedding import search_with_expansion, search_similar
from app.services import cache

logger = logging.getLogger(__name__)
settings = get_settings()

# Cache TTL constants
RECOMMEND_TTL = 5 * 60    # 5 min
INTERACT_TTL  = 30 * 60   # 30 min — interact ke baad zyada time tak cache rakho


def _build_query(user: User) -> str:
    return " ".join(user.interests or []) or "general news"


def _get_excluded_ids(db: Session, user_id: int) -> List[str]:
    logs = (
        db.query(InteractionLog)
        .filter(
            InteractionLog.user_id == user_id,
            InteractionLog.action.in_(["viewed", "liked", "skipped"]),
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

    cache_key = cache.make_recommend_key(user_id)
    cached    = cache.get(cache_key)
    if cached:
        logger.info(f"Cache hit for user={user.username}")
        return user, cached

    user_interests = user.interests or []
    excluded       = _get_excluded_ids(db, user_id)

    logger.info(
        f"Recommending for user={user.username} "
        f"interests={user_interests} excluded={len(excluded)}"
    )

    if user_interests:
        results = search_with_expansion(
            user_interests=user_interests,
            top_n=settings.top_n_results,
            exclude_ids=excluded,
        )
    else:
        results = search_similar(
            query_text="general news today",
            top_n=settings.top_n_results,
            exclude_ids=excluded,
        )

    if results:
        cache.set(cache_key, results, ttl=RECOMMEND_TTL)

    return user, results


def invalidate_user_cache(user_id: int) -> None:
    """Interact ke baad sirf recommend cache delete karo — groq cache rakho."""
    cache.delete(cache.make_recommend_key(user_id))


def invalidate_all_user_cache(user_id: int) -> None:
    """Interest change hone par sab kuch delete karo."""
    cache.delete(cache.make_recommend_key(user_id))
    cache.delete(cache.make_groq_key(user_id))


def log_interaction(db: Session, user_id: int, article_id: str, action: str) -> None:
    db.add(InteractionLog(user_id=user_id, article_id=article_id, action=action))
    db.commit()
    # ── Smart cache invalidation ───────────────────────────
    # Sirf recommend cache invalidate karo
    # Groq summary cache rakho — woh change nahi hoti interact se
    invalidate_user_cache(user_id)