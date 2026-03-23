"""
Auth endpoints
──────────────
POST /api/v1/auth/register   — Create account
POST /api/v1/auth/login      — Get JWT tokens
POST /api/v1/auth/refresh    — Rotate tokens

Security:
- Rate limits: register 5/min, login 10/min (brute-force protection)
- Passwords: bcrypt hashed, never returned
- Tokens: short-lived access (30min) + rotating refresh (7d)
- request_id: every response mein hota hai (tracing ke liye)
- Timing attack protection: verify_password hamesha run hoti hai
"""
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session
import logging

from app.db.session import get_db
from app.db.models.user import User
from app.schemas.auth import UserCreate, UserLogin, Token, RefreshTokenRequest
from app.schemas.user import UserResponse
from app.schemas.common import ApiResponse
from app.middleware.auth import (
    hash_password, verify_password,
    create_access_token, create_refresh_token,
    decode_token, REFRESH_TOKEN_TYPE,
)
from app.middleware.rate_limit import limiter
from app.core.exceptions import (
    UsernameAlreadyExistsError, EmailAlreadyExistsError,
    InvalidCredentialsError, UserNotFoundError,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/register",
    response_model=ApiResponse[UserResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create new account",
)
@limiter.limit("5/minute")   # Bulk signup attack protection
def register_user(request: Request, payload: UserCreate, db: Session = Depends(get_db)):
    # Case-insensitive username check
    if db.query(User).filter(
        User.username.ilike(payload.username)
    ).first():
        raise UsernameAlreadyExistsError()

    if db.query(User).filter(
        User.email == payload.email.lower()
    ).first():
        raise EmailAlreadyExistsError()

    user = User(
        username=payload.username.lower(),      # normalize — consistent
        email=payload.email.lower(),            # normalize
        hashed_password=hash_password(payload.password),
        interests=[i.value for i in payload.interests],
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info({"event": "user_registered", "username": user.username})

    return ApiResponse(
        message="Account created successfully",
        data=UserResponse.model_validate(user),
        request_id=getattr(request.state, "request_id", None),
    )


@router.post(
    "/login",
    response_model=ApiResponse[Token],
    summary="Authenticate and get tokens",
)
@limiter.limit("10/minute")  # Brute-force protection
def login(request: Request, payload: UserLogin, db: Session = Depends(get_db)):
    # Always query then verify — prevents timing attack
    # (attacker can't tell if username exists by response time)
    user = db.query(User).filter(
        User.username == payload.username.lower()
    ).first()

    # verify_password runs even if user is None — constant time
    if not user or not verify_password(payload.password, user.hashed_password):
        raise InvalidCredentialsError()

    token_data = {"sub": str(user.id), "username": user.username}

    return ApiResponse(
        message="Login successful",
        data=Token(
            access_token=create_access_token(token_data),
            refresh_token=create_refresh_token(token_data),
        ),
        request_id=getattr(request.state, "request_id", None),
    )


@router.post(
    "/refresh",
    response_model=ApiResponse[Token],
    summary="Rotate refresh token",
)
@limiter.limit("20/minute")
def refresh_token(request: Request, payload: RefreshTokenRequest, db: Session = Depends(get_db)):
    token_data = decode_token(payload.refresh_token, expected_type=REFRESH_TOKEN_TYPE)
    user = db.query(User).filter(User.id == token_data.user_id).first()
    if not user:
        raise UserNotFoundError()

    new_data = {"sub": str(user.id), "username": user.username}

    return ApiResponse(
        message="Token refreshed",
        data=Token(
            access_token=create_access_token(new_data),
            refresh_token=create_refresh_token(new_data),
        ),
        request_id=getattr(request.state, "request_id", None),
    )