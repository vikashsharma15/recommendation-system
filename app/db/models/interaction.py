from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from app.db.base import Base


class InteractionLog(Base):
    __tablename__ = "interaction_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    article_id = Column(String, nullable=False)
    action = Column(String, default="viewed")   # viewed | liked | skipped
    timestamp = Column(DateTime, default=datetime.utcnow)