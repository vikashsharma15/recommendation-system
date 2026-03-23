import html
import re
from pydantic import BaseModel, field_validator
from typing import List, Optional
from app.core.constants import InteractionAction


def _clean_text(text: str) -> str:
    """HTML entities decode + special chars clean karo."""
    if not text:
        return text
    # HTML entities decode
    text = html.unescape(text)
    # &#39; #39; #146; #151; quot; amp; etc
    text = re.sub(r'#\d+;?', '', text)
    text = re.sub(r'&[a-zA-Z]+;', '', text)
    # Extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


class ArticleOut(BaseModel):
    article_id: str
    title: str
    description: str
    category: Optional[str] = None
    score: float
    url: Optional[str] = None  # ← add kiya

    @field_validator('title', mode='before')
    @classmethod
    def clean_title(cls, v):
        return _clean_text(v) if v else v

    @field_validator('description', mode='before')
    @classmethod
    def clean_description(cls, v):
        return _clean_text(v) if v else v


class RecommendResponse(BaseModel):
    user_id: int
    username: str
    recommendations: List[ArticleOut]
    groq_summary: Optional[str] = None


class InteractionCreate(BaseModel):
    article_id: str
    action: InteractionAction = InteractionAction.viewed