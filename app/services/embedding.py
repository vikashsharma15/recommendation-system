import chromadb
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any
import logging

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_model: SentenceTransformer = None
_chroma_client: chromadb.PersistentClient = None
_collection = None

COLLECTION_NAME = "articles"
EMBED_BATCH_SIZE = 256
CHROMA_BATCH_SIZE = 5000


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        logger.info(f"Loading HF model: {settings.hf_model_name}")
        _model = SentenceTransformer(settings.hf_model_name)
        logger.info("Model loaded successfully")
    return _model


def get_chroma_collection():
    global _chroma_client, _collection
    if _collection is None:
        _chroma_client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
        _collection = _chroma_client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(f"Chroma collection ready. Articles indexed: {_collection.count()}")
    return _collection


def embed_texts(texts: List[str]) -> List[List[float]]:
    embeddings = get_model().encode(
        texts,
        show_progress_bar=False,
        normalize_embeddings=True,
    )
    return embeddings.tolist()


def index_articles(articles: List[Dict[str, Any]]) -> int:
    collection = get_chroma_collection()

    existing_ids: set = set()
    if collection.count() > 0:
        existing_ids = set(collection.get(include=[])["ids"])

    new_articles = [a for a in articles if a["id"] not in existing_ids]
    if not new_articles:
        logger.info("All articles already indexed.")
        return 0

    texts = [f"{a['title']}. {a['description']}" for a in new_articles]
    ids = [a["id"] for a in new_articles]
    metadatas = [
        {
            "title": a["title"],
            "description": a["description"],
            "category": a.get("category", ""),
        }
        for a in new_articles
    ]

    all_embeddings: List[List[float]] = []
    for i in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[i : i + EMBED_BATCH_SIZE]
        all_embeddings.extend(embed_texts(batch))
        logger.info(f"Embedded batch {i // EMBED_BATCH_SIZE + 1}/{(len(texts) - 1) // EMBED_BATCH_SIZE + 1}")

    for i in range(0, len(ids), CHROMA_BATCH_SIZE):
        collection.add(
            ids=ids[i : i + CHROMA_BATCH_SIZE],
            embeddings=all_embeddings[i : i + CHROMA_BATCH_SIZE],
            metadatas=metadatas[i : i + CHROMA_BATCH_SIZE],
        )
        logger.info(f"Saved to ChromaDB {min(i + CHROMA_BATCH_SIZE, len(ids))}/{len(ids)}")

    logger.info(f"Indexed {len(new_articles)} new articles.")
    return len(new_articles)


def search_similar(
    query_text: str,
    top_n: int = 10,
    exclude_ids: List[str] = None,
) -> List[Dict]:
    collection = get_chroma_collection()

    if collection.count() == 0:
        return []

    query_embedding = embed_texts([query_text])[0]
    exclude_ids = exclude_ids or []

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_n + len(exclude_ids), collection.count()),
        include=["metadatas", "distances"],
    )

    articles = []
    for i, doc_id in enumerate(results["ids"][0]):
        if doc_id in exclude_ids:
            continue

        meta = results["metadatas"][0][i]
        score = round(1 - results["distances"][0][i], 4)

        articles.append({
            "article_id": doc_id,
            "title": meta.get("title", ""),
            "description": meta.get("description", ""),
            "category": meta.get("category", ""),
            "score": score,
        })

        if len(articles) >= top_n:
            break

    return articles