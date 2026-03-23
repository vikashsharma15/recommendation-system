from pydantic import BaseModel, field_validator
from typing import List, Optional
from datetime import datetime
from app.core.constants import InterestCategory, MAX_INTERESTS, MIN_INTERESTS


class UserResponse(BaseModel):
    id:         int
    username:   str
    full_name:  Optional[str] = None
    email:      str
    interests:  List[str]
    created_at: datetime
    bio:        Optional[str] = None
    avatar_url: Optional[str] = None
    cover_url:  Optional[str] = None
    twitter:    Optional[str] = None
    linkedin:   Optional[str] = None
    github:     Optional[str] = None
    # Username change info for frontend
    username_change_count:  int = 0
    username_changed_at:    Optional[datetime] = None

    model_config = {"from_attributes": True}


class PreferenceUpdate(BaseModel):
    interests: List[InterestCategory]

    @field_validator("interests")
    @classmethod
    def validate_interests(cls, v):
        if len(v) < MIN_INTERESTS:
            raise ValueError(f"At least {MIN_INTERESTS} interest required")
        if len(v) > MAX_INTERESTS:
            raise ValueError(f"Maximum {MAX_INTERESTS} interests allowed")
        return list(set(v))


class ProfileUpdate(BaseModel):
    full_name:  Optional[str] = None
    bio:        Optional[str] = None
    avatar_url: Optional[str] = None
    cover_url:  Optional[str] = None
    twitter:    Optional[str] = None
    linkedin:   Optional[str] = None
    github:     Optional[str] = None

    @field_validator("bio")
    @classmethod
    def validate_bio(cls, v):
        if v and len(v) > 200:
            raise ValueError("Bio must be at most 200 characters")
        return v

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v):
        if v and len(v) > 60:
            raise ValueError("Full name must be at most 60 characters")
        return v


class UsernameUpdate(BaseModel):
    """Username change — max 2 times per month."""
    username: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, v):
        import re
        if len(v) < 3 or len(v) > 30:
            raise ValueError("Username must be 3-30 characters")
        if not re.match(r'^[a-zA-Z0-9_]+$', v):
            raise ValueError("Letters, numbers and underscores only")
        return v.lower()