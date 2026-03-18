from slowapi import Limiter
from slowapi.util import get_remote_address
from app.core.config import get_settings

settings = get_settings()

# Uses client IP as key — no Redis needed, in-memory
limiter = Limiter(key_func=get_remote_address)