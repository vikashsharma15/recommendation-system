from fastapi import APIRouter
import logging

from app.schemas.common import IngestStatus

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/status", response_model=IngestStatus)
def articles_status():
    """Check how many articles are indexed in ChromaDB."""
    try:
        from app.services.embedding import get_chroma_collection
        collection = get_chroma_collection()
        count = collection.count()
        return IngestStatus(
            status="ready" if count > 0 else "empty",
            articles_indexed=count,
            message=f"{count} articles indexed" if count > 0 else "Run ingest script first",
        )
    except Exception as e:
        return IngestStatus(status="error", articles_indexed=0, message=str(e))