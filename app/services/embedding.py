import logging
from typing import List, Dict, Any

from sentence_transformers import SentenceTransformer

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_model: SentenceTransformer = None

EMBED_BATCH_SIZE = 256
CHROMA_BATCH_SIZE = 5000


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        logger.info(f"Loading HF model: {settings.hf_model_name}")
        _model = SentenceTransformer(settings.hf_model_name)
        logger.info("Model loaded successfully")
    return _model


def embed_texts(texts: List[str]) -> List[List[float]]:
    embeddings = get_model().encode(
        texts,
        show_progress_bar=False,
        normalize_embeddings=True,
    )
    return embeddings.tolist()


def _use_pinecone() -> bool:
    return bool(settings.pinecone_api_key)


def _get_pinecone_index():
    from pinecone import Pinecone
    pc = Pinecone(api_key=settings.pinecone_api_key)
    return pc.Index(settings.pinecone_index)


def _get_chroma_collection():
    import chromadb
    client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
    collection = client.get_or_create_collection(
        name="articles",
        metadata={"hnsw:space": "cosine"},
    )
    logger.info(f"Chroma collection ready. Articles indexed: {collection.count()}")
    return collection


def get_chroma_collection():
    return _get_chroma_collection()


def index_articles(articles: List[Dict[str, Any]]) -> int:
    if _use_pinecone():
        return _index_pinecone(articles)
    return _index_chroma(articles)


def search_similar(
    query_text: str,
    top_n: int = 10,
    exclude_ids: List[str] = None,
) -> List[Dict]:
    if _use_pinecone():
        return _search_pinecone(query_text, top_n, exclude_ids or [])
    return _search_chroma(query_text, top_n, exclude_ids or [])


# ── Pinecone ────────────────────────────────────────────────

def _index_pinecone(articles: List[Dict[str, Any]]) -> int:
    index = _get_pinecone_index()

    existing = set()
    try:
        stats = index.describe_index_stats()
        if stats.total_vector_count > 0:
            fetch_result = index.fetch(ids=[a["id"] for a in articles[:100]])
            existing = set(fetch_result.vectors.keys())
    except Exception:
        pass

    new_articles = [a for a in articles if a["id"] not in existing]
    if not new_articles:
        logger.info("All articles already indexed in Pinecone.")
        return 0

    texts = [f"{a['title']}. {a['description']}" for a in new_articles]

    all_embeddings: List[List[float]] = []
    for i in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[i : i + EMBED_BATCH_SIZE]
        all_embeddings.extend(embed_texts(batch))
        logger.info(f"Embedded batch {i // EMBED_BATCH_SIZE + 1}/{(len(texts) - 1) // EMBED_BATCH_SIZE + 1}")

    pinecone_batch = 100
    for i in range(0, len(new_articles), pinecone_batch):
        batch = new_articles[i : i + pinecone_batch]
        vectors = [
            {
                "id": a["id"],
                "values": all_embeddings[i + j],
                "metadata": {
                    "title": a["title"],
                    "description": a["description"],
                    "category": a.get("category", ""),
                },
            }
            for j, a in enumerate(batch)
        ]
        index.upsert(vectors=vectors)
        logger.info(f"Upserted to Pinecone {min(i + pinecone_batch, len(new_articles))}/{len(new_articles)}")

    logger.info(f"Indexed {len(new_articles)} articles to Pinecone.")
    return len(new_articles)


def _search_pinecone(query_text: str, top_n: int, exclude_ids: List[str]) -> List[Dict]:
    index = _get_pinecone_index()
    query_embedding = embed_texts([query_text])[0]

    results = index.query(
        vector=query_embedding,
        top_k=top_n + len(exclude_ids),
        include_metadata=True,
    )

    articles = []
    for match in results.matches:
        if match.id in exclude_ids:
            continue
        articles.append({
            "article_id": match.id,
            "title": match.metadata.get("title", ""),
            "description": match.metadata.get("description", ""),
            "category": match.metadata.get("category", ""),
            "score": round(match.score, 4),
        })
        if len(articles) >= top_n:
            break

    return articles


# ── ChromaDB ────────────────────────────────────────────────

def _index_chroma(articles: List[Dict[str, Any]]) -> int:
    collection = _get_chroma_collection()

    existing_ids: set = set()
    if collection.count() > 0:
        existing_ids = set(collection.get(include=[])["ids"])

    new_articles = [a for a in articles if a["id"] not in existing_ids]
    if not new_articles:
        logger.info("All articles already indexed in ChromaDB.")
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

    logger.info(f"Indexed {len(new_articles)} articles to ChromaDB.")
    return len(new_articles)


def _search_chroma(query_text: str, top_n: int, exclude_ids: List[str]) -> List[Dict]:
    collection = _get_chroma_collection()

    if collection.count() == 0:
        return []

    query_embedding = embed_texts([query_text])[0]

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