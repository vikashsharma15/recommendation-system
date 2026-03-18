from pydantic import BaseModel
from typing import List, Optional


class ArticleOut(BaseModel):
    article_id: str
    title: str
    description: str
    category: Optional[str] = None
    score: float


class RecommendResponse(BaseModel):
    user_id: int
    username: str
    recommendations: List[ArticleOut]
    groq_summary: Optional[str] = None


class InteractionCreate(BaseModel):
    article_id: str
    action: str = "viewed"   # viewed | liked | skipped