from pydantic import BaseModel, field_validator
from typing import List, Optional

from app.core.constants import (
    InterestCategory,
    USERNAME_REGEX,
    EMAIL_REGEX,
    MIN_USERNAME_LENGTH,
    MAX_USERNAME_LENGTH,
    MIN_PASSWORD_LENGTH,
    MAX_PASSWORD_LENGTH,
    MAX_EMAIL_LENGTH,
    MAX_EMAIL_LOCAL_LENGTH,
    PASSWORD_UPPERCASE_REGEX,
    PASSWORD_NUMBER_REGEX,
    MIN_INTERESTS,
    MAX_INTERESTS,
    BLOCKED_EMAIL_DOMAINS,
    STRICT_DOMAINS,
)


class UserCreate(BaseModel):
    username: str
    full_name: Optional[str] = None
    email: str
    password: str
    interests: List[InterestCategory]

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        v = v.strip()
        if len(v) < MIN_USERNAME_LENGTH:
            raise ValueError(f"Username must be at least {MIN_USERNAME_LENGTH} characters")
        if len(v) > MAX_USERNAME_LENGTH:
            raise ValueError(f"Username must be at most {MAX_USERNAME_LENGTH} characters")
        if not USERNAME_REGEX.match(v):
            raise ValueError("Username can only contain letters, numbers and underscores")
        return v.lower()

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip()

        # Length checks
        if len(v) > MAX_EMAIL_LENGTH:
            raise ValueError(f"Email must be at most {MAX_EMAIL_LENGTH} characters")

        local_part = v.split("@")[0]
        if len(local_part) > MAX_EMAIL_LOCAL_LENGTH:
            raise ValueError(f"Email username part must be at most {MAX_EMAIL_LOCAL_LENGTH} characters")

        # Format check
        if not EMAIL_REGEX.match(v):
            raise ValueError("Invalid email format")

        domain = v.split("@")[-1].lower()

        # Blocked disposable domains
        if domain in BLOCKED_EMAIL_DOMAINS:
            raise ValueError(f"Email domain '{domain}' is not allowed")

        # Strict domain typo check
        # e.g. gmail12.com, gmai.com, yahooo.com → rejected
        for strict in STRICT_DOMAINS:
            base = strict.split(".")[0]
            if base in domain and domain != strict:
                raise ValueError(
                    f"'{domain}' is not a valid email domain. Did you mean '{strict}'?"
                )

        return v.lower()

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < MIN_PASSWORD_LENGTH:
            raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
        if len(v) > MAX_PASSWORD_LENGTH:
            raise ValueError(f"Password must be at most {MAX_PASSWORD_LENGTH} characters")
        if not PASSWORD_UPPERCASE_REGEX.search(v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not PASSWORD_NUMBER_REGEX.search(v):
            raise ValueError("Password must contain at least one number")
        return v

    @field_validator("interests")
    @classmethod
    def validate_interests(cls, v: List[InterestCategory]) -> List[InterestCategory]:
        if len(v) < MIN_INTERESTS:
            raise ValueError(f"At least {MIN_INTERESTS} interest required")
        if len(v) > MAX_INTERESTS:
            raise ValueError(f"Maximum {MAX_INTERESTS} interests allowed")
        return list(set(v))


class UserLogin(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class TokenData(BaseModel):
    user_id: Optional[int] = None
    username: Optional[str] = None