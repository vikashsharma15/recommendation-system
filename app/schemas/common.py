from pydantic import BaseModel


class IngestStatus(BaseModel):
    status: str
    articles_indexed: int
    message: str