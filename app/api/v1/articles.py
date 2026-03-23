from fastapi import APIRouter
import logging

from app.schemas.common import ApiResponse, IngestStatus
from app.core.constants import InterestCategory

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/categories", response_model=ApiResponse)
def get_categories():
    """Available interest categories for registration."""
    return ApiResponse(
        message="Categories fetched successfully",
        data={"categories": [c.value for c in InterestCategory]},
    )


@router.get("/status", response_model=ApiResponse[IngestStatus])
def articles_status():
    """Check how many articles are indexed in vector DB."""
    try:
        from app.services.embedding import get_chroma_collection
        collection = get_chroma_collection()
        count = collection.count()
        status_data = IngestStatus(
            status="ready" if count > 0 else "empty",
            articles_indexed=count,
            message=f"{count} articles indexed" if count > 0 else "Run ingest script first",
        )
        return ApiResponse(message="Status fetched successfully", data=status_data)
    except Exception as e:
        return ApiResponse(
            success=False,
            message=str(e),
            data=IngestStatus(status="error", articles_indexed=0, message=str(e)),
        )