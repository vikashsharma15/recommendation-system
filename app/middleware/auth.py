import warnings
warnings.filterwarnings("ignore", ".*error reading bcrypt version.*")
warnings.filterwarnings("ignore", ".*trapped.*")

from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import TokenInvalidError, UserNotFoundError
from app.db.session import get_db
from app.db.models.user import User
from app.schemas.auth import TokenData

settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
http_bearer = HTTPBearer()

ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain[:72])


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain[:72], hashed)


def _create_token(data: dict, token_type: str, expires_minutes: int) -> str:
    to_encode = data.copy()
    to_encode.update({
        "exp": datetime.utcnow() + timedelta(minutes=expires_minutes),
        "type": token_type,
    })
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def create_access_token(data: dict) -> str:
    return _create_token(data, ACCESS_TOKEN_TYPE, settings.access_token_expire_minutes)


def create_refresh_token(data: dict) -> str:
    return _create_token(data, REFRESH_TOKEN_TYPE, settings.access_token_expire_minutes)


def decode_token(token: str, expected_type: str = ACCESS_TOKEN_TYPE) -> TokenData:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        if payload.get("type") != expected_type:
            raise TokenInvalidError()
        user_id = payload.get("sub")
        username = payload.get("username")
        if user_id is None:
            raise TokenInvalidError()
        return TokenData(user_id=int(user_id), username=username)
    except JWTError:
        raise TokenInvalidError()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(http_bearer),
    db: Session = Depends(get_db),
) -> User:
    token_data = decode_token(credentials.credentials, ACCESS_TOKEN_TYPE)
    user = db.query(User).filter(User.id == token_data.user_id).first()
    if not user:
        raise UserNotFoundError()
    return user