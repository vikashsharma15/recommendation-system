from pydantic import BaseModel
from typing import List
from datetime import datetime


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    interests: List[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class PreferenceUpdate(BaseModel):
    interests: List[str]