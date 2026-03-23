from pydantic import BaseModel
from typing import Any, Generic, Optional, List, TypeVar
from datetime import datetime, timezone

T = TypeVar("T")


class ErrorDetail(BaseModel):
    field: Optional[str] = None
    issue: Optional[str] = None
    message: str


class ErrorBody(BaseModel):
    code: str
    message: str
    status: int
    details: Optional[List[ErrorDetail]] = None


class Meta(BaseModel):
    page: Optional[int] = None
    page_size: Optional[int] = None
    total: Optional[int] = None
    timestamp: str = ""

    def model_post_init(self, __context: Any) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


class ApiResponse(BaseModel, Generic[T]):
    success: bool = True
    message: str
    data: Optional[T] = None
    meta: Optional[Meta] = None
    request_id: Optional[str] = None


class ErrorResponse(BaseModel):
    success: bool = False
    error: ErrorBody
    request_id: Optional[str] = None


class IngestStatus(BaseModel):
    status: str
    articles_indexed: int
    message: str