from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import logging

from app.db.session import get_db
from app.db.models import User
from app.schemas.user import UserResponse, PreferenceUpdate
from app.middleware.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Get your own profile. Requires JWT token."""
    return current_user


@router.put("/me/preferences", response_model=UserResponse)
def update_preferences(
    payload: PreferenceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update your interests. Requires JWT token."""
    current_user.interests = payload.interests
    db.commit()
    db.refresh(current_user)
    logger.info(f"Updated interests for: {current_user.username}")
    return current_user