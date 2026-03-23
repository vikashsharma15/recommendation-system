from fastapi import APIRouter, Depends, Request, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import logging

from app.db.session import get_db
from app.db.models.user import User
from app.schemas.user import UserResponse, PreferenceUpdate, ProfileUpdate, UsernameUpdate
from app.schemas.common import ApiResponse
from app.middleware.auth import get_current_user
from app.services.recommendation import invalidate_all_user_cache
from app.core.config import get_settings

logger   = logging.getLogger(__name__)
router   = APIRouter()
settings = get_settings()


@router.get("/me", response_model=ApiResponse[UserResponse])
def get_me(request: Request, current_user: User = Depends(get_current_user)):
    return ApiResponse(
        message="User profile fetched successfully",
        data=UserResponse.model_validate(current_user),
        request_id=getattr(request.state, "request_id", None),
    )


@router.patch("/me", response_model=ApiResponse[UserResponse])
def update_profile(
    request:      Request,
    payload:      ProfileUpdate,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(current_user, field, value)
    db.commit()
    db.refresh(current_user)
    logger.info({"event": "profile_updated", "username": current_user.username})

    return ApiResponse(
        message="Profile updated successfully",
        data=UserResponse.model_validate(current_user),
        request_id=getattr(request.state, "request_id", None),
    )


@router.patch("/me/username", response_model=ApiResponse[UserResponse])
def change_username(
    request:      Request,
    payload:      UsernameUpdate,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    """
    Username change — max 2 times per calendar month.
    """
    now = datetime.now(timezone.utc)
    limit = settings.username_change_limit_per_month

    # Check monthly limit
    if current_user.username_changed_at:
        last = current_user.username_changed_at
        if hasattr(last, 'tzinfo') and last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)

        same_month = (last.year == now.year and last.month == now.month)
        count = current_user.username_change_count or 0

        if same_month and count >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Username can only be changed {limit} times per month. Try next month."
            )
        # New month — reset count
        if not same_month:
            current_user.username_change_count = 0

    # Check uniqueness
    existing = db.query(User).filter(
        User.username == payload.username,
        User.id != current_user.id
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken"
        )

    old_username = current_user.username
    current_user.username = payload.username
    current_user.username_changed_at   = now
    current_user.username_change_count = (current_user.username_change_count or 0) + 1
    db.commit()
    db.refresh(current_user)

    logger.info({"event": "username_changed", "old": old_username, "new": payload.username})

    return ApiResponse(
        message="Username updated",
        data=UserResponse.model_validate(current_user),
        request_id=getattr(request.state, "request_id", None),
    )


@router.put("/me/preferences", response_model=ApiResponse[UserResponse])
def update_preferences(
    request:      Request,
    payload:      PreferenceUpdate,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    current_user.interests = [i.value for i in payload.interests]
    db.commit()
    db.refresh(current_user)
    invalidate_all_user_cache(current_user.id)
    logger.info({"event": "preferences_updated", "username": current_user.username})

    return ApiResponse(
        message="Preferences updated successfully",
        data=UserResponse.model_validate(current_user),
        request_id=getattr(request.state, "request_id", None),
    )