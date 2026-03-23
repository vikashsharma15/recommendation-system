from sqlalchemy import Column, Integer, String, DateTime, JSON, Text
from datetime import datetime
from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id                = Column(Integer, primary_key=True, index=True)
    username          = Column(String, unique=True, index=True, nullable=False)
    email             = Column(String, unique=True, nullable=False)
    hashed_password   = Column(String, nullable=False)
    interests         = Column(JSON, default=list)
    created_at        = Column(DateTime, default=datetime.utcnow)

    # Profile
    full_name         = Column(String, nullable=True)    # display name
    bio               = Column(Text, nullable=True)
    avatar_url        = Column(String, nullable=True)
    cover_url         = Column(String, nullable=True)
    twitter           = Column(String, nullable=True)
    linkedin          = Column(String, nullable=True)
    github            = Column(String, nullable=True)

    # Username change tracking
    username_changed_at    = Column(DateTime, nullable=True)
    username_change_count  = Column(Integer, default=0, nullable=False)