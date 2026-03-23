import logging
from typing import List, Dict, Any, Optional

from sentence_transformers import SentenceTransformer
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_model: Optional[SentenceTransformer] = None

# ── All constants from settings (.env) ────────────────────
# Hardcoded values nahi — config se uthao
# .env mein change karo, code touch mat karo
EMBED_BATCH_SIZE      = settings.embed_batch_size
CHROMA_BATCH_SIZE     = settings.chroma_batch_size
SIMILARITY_THRESHOLD  = settings.similarity_threshold
RETRIEVE_MULTIPLIER   = settings.retrieve_multiplier
CATEGORY_BOOST        = settings.category_boost


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        logger.info(f"Loading HF model: {settings.hf_model_name}")
        _model = SentenceTransformer(settings.hf_model_name)
        logger.info("Model loaded")
    return _model


def embed_texts(texts: List[str]) -> List[List[float]]:
    return get_model().encode(
        texts,
        show_progress_bar=False,
        normalize_embeddings=True,
    ).tolist()


# ══════════════════════════════════════════════════════════
# HyDE — Hypothetical Document Embedding
# ──────────────────────────────────────────────────────────
# Problem: User query "sports" ek short question hai.
#          Pinecone mein indexed articles paragraph-style hain.
#          Vector space mein dono door hote hain — retrieval weak hoti hai.
#
# Fix: Query ki jagah ek hypothetical article-style paragraph banao.
#      Yeh document vectors ke paas hoga — retrieval accurate hogi.
# ══════════════════════════════════════════════════════════
def _build_expansion_queries(interest: str) -> List[str]:
    """Dynamic expansion — koi bhi interest handle karta hai."""
    i = interest.strip()
    return [f"{i} news analysis updates developments"]


def _build_hyde_query(user_interests: List[str]) -> str:
    joined = ", ".join(user_interests)
    return (
        f"Top stories and breaking news about {joined}. "
        f"Expert analysis on recent developments in {joined}. "
        f"Latest updates, key statistics, and insights from leading sources on {joined}."
    )


# ── Router ────────────────────────────────────────────────
def _use_pinecone() -> bool:
    return bool(settings.pinecone_api_key) and settings.use_pinecone


def _get_pinecone_index():
    from pinecone import Pinecone
    return Pinecone(api_key=settings.pinecone_api_key).Index(settings.pinecone_index)


def _get_chroma_collection():
    import chromadb
    client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
    return client.get_or_create_collection(
        name="articles",
        metadata={"hnsw:space": "cosine"},
    )


def get_chroma_collection():
    return _get_chroma_collection()


# ── Public indexing API ───────────────────────────────────
def index_articles(articles: List[Dict[str, Any]]) -> int:
    if _use_pinecone():
        return _index_pinecone(articles)
    return _index_chroma(articles)


# ── Public search API ─────────────────────────────────────
def search_similar(
    query_text: str,
    top_n: int = 10,
    exclude_ids: List[str] = None,
    user_interests: List[str] = None,
    use_hyde: bool = True,
) -> List[Dict]:
    """
    3-stage improved retrieval:

    Stage 1 — HyDE
      User interests se hypothetical paragraph banao.
      Plain query ki jagah yeh embed karo.
      Document-space ke paas → better cosine similarity.

    Stage 2 — Oversampling + threshold
      top_n * RETRIEVE_MULTIPLIER articles fetch karo.
      Score < SIMILARITY_THRESHOLD wale drop karo.
      Garbage results feed mein nahi aate.

    Stage 3 — Category boost reranking
      Agar article ki category user ke interest mein hai
      toh score mein CATEGORY_BOOST add karo.
      Final sort by score.
    """
    exclude_ids = exclude_ids or []

    # Stage 1: HyDE
    if use_hyde and user_interests:
        search_text = _build_hyde_query(user_interests)
        logger.debug(f"HyDE active: {search_text[:80]}...")
    else:
        search_text = query_text

    # Stage 2: Oversample
    fetch_n = top_n * RETRIEVE_MULTIPLIER
    if _use_pinecone():
        raw = _search_pinecone(search_text, fetch_n, exclude_ids)
    else:
        raw = _search_chroma(search_text, fetch_n, exclude_ids)

    # Threshold filter
    filtered = [r for r in raw if r["score"] >= SIMILARITY_THRESHOLD]

    # Stage 3: Category boost
    if user_interests:
        interest_lower = [i.lower() for i in user_interests]
        for r in filtered:
            cat = r.get("category", "").lower()
            if any(cat in i or i in cat for i in interest_lower):
                r["score"] = min(1.0, round(r["score"] + CATEGORY_BOOST, 4))

    filtered.sort(key=lambda x: x["score"], reverse=True)

    logger.info(
        f"search_similar | fetched={len(raw)} after_threshold={len(filtered)} "
        f"hyde={use_hyde and bool(user_interests)} threshold={SIMILARITY_THRESHOLD}"
    )

    return filtered[:top_n]


# ── Pinecone ──────────────────────────────────────────────
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
        logger.info("All already indexed in Pinecone.")
        return 0

    # Rich text — category bhi embed karo for better clustering
    texts = [
        f"{a['title']}. {a.get('description', '')}. Category: {a.get('category', '')}."
        for a in new_articles
    ]

    all_embeddings: List[List[float]] = []
    for i in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[i: i + EMBED_BATCH_SIZE]
        all_embeddings.extend(embed_texts(batch))
        logger.info(f"Embedding {min(i + EMBED_BATCH_SIZE, len(texts))}/{len(texts)}")

    for i in range(0, len(new_articles), 100):
        batch = new_articles[i: i + 100]
        vectors = [
            {
                "id": a["id"],
                "values": all_embeddings[i + j],
                "metadata": {
                    "title": a["title"],
                    "description": a.get("description", ""),
                    "category": a.get("category", ""),
                    "url": a.get("url", ""),
                },
            }
            for j, a in enumerate(batch)
        ]
        index.upsert(vectors=vectors)

    logger.info(f"Indexed {len(new_articles)} to Pinecone.")
    return len(new_articles)


def _search_pinecone(
    query_text: str,
    top_n: int,
    exclude_ids: List[str],
) -> List[Dict]:
    index = _get_pinecone_index()
    query_vec = embed_texts([query_text])[0]

    results = index.query(
        vector=query_vec,
        top_k=top_n + len(exclude_ids),
        include_metadata=True,
    )

    return [
        {
            "article_id": m.id,
            "title":       m.metadata.get("title", ""),
            "description": m.metadata.get("description", ""),
            "category":    m.metadata.get("category", ""),
            "url":         m.metadata.get("url", ""),
            "score":       round(m.score, 4),
        }
        for m in results.matches
        if m.id not in exclude_ids
    ]


# ── ChromaDB ──────────────────────────────────────────────
def _index_chroma(articles: List[Dict[str, Any]]) -> int:
    collection = _get_chroma_collection()

    existing_ids: set = set()
    if collection.count() > 0:
        existing_ids = set(collection.get(include=[])["ids"])

    new_articles = [a for a in articles if a["id"] not in existing_ids]
    if not new_articles:
        logger.info("All already indexed in ChromaDB.")
        return 0

    texts = [
        f"{a['title']}. {a.get('description', '')}. Category: {a.get('category', '')}."
        for a in new_articles
    ]

    all_embeddings: List[List[float]] = []
    for i in range(0, len(texts), EMBED_BATCH_SIZE):
        all_embeddings.extend(embed_texts(texts[i: i + EMBED_BATCH_SIZE]))

    for i in range(0, len(new_articles), CHROMA_BATCH_SIZE):
        collection.add(
            ids=[a["id"] for a in new_articles[i: i + CHROMA_BATCH_SIZE]],
            embeddings=all_embeddings[i: i + CHROMA_BATCH_SIZE],
            metadatas=[
                {
                    "title": a["title"],
                    "description": a.get("description", ""),
                    "category": a.get("category", ""),
                    "url": a.get("url", ""),
                }
                for a in new_articles[i: i + CHROMA_BATCH_SIZE]
            ],
        )

    logger.info(f"Indexed {len(new_articles)} to ChromaDB.")
    return len(new_articles)


def _search_chroma(
    query_text: str,
    top_n: int,
    exclude_ids: List[str],
) -> List[Dict]:
    collection = _get_chroma_collection()
    if collection.count() == 0:
        return []

    query_vec = embed_texts([query_text])[0]
    results = collection.query(
        query_embeddings=[query_vec],
        n_results=min(top_n + len(exclude_ids), collection.count()),
        include=["metadatas", "distances"],
    )

    return [
        {
            "article_id": doc_id,
            "title":       results["metadatas"][0][i].get("title", ""),
            "description": results["metadatas"][0][i].get("description", ""),
            "category":    results["metadatas"][0][i].get("category", ""),
            "url":         results["metadatas"][0][i].get("url", ""),
            "score":       round(1 - results["distances"][0][i], 4),
        }
        for i, doc_id in enumerate(results["ids"][0])
        if doc_id not in exclude_ids
    ]


# ══════════════════════════════════════════════════════════
# Query Expansion — mismatch fix
# ──────────────────────────────────────────────────────────
# Problem: "Sports" → low match with "Premier League analysis"
# Fix: Multiple query variants banao, sab retrieve karo, merge karo
# ══════════════════════════════════════════════════════════

# Category-wise synonyms/expansions
CATEGORY_EXPANSIONS: Dict[str, List[str]] = {
    "sports": [
        "football soccer cricket basketball tennis match tournament",
        "athlete player team score championship league",
        "sports news results standings fixtures",
    ],
    "business": [
        "stock market economy finance investment startup",
        "company earnings revenue profit loss quarterly results",
        "CEO merger acquisition IPO valuation funding",
    ],
    "world": [
        "international news politics government policy",
        "election president prime minister war conflict",
        "global affairs diplomacy foreign relations",
    ],
    "science/technology": [
        "AI artificial intelligence machine learning research",
        "tech company software product launch innovation",
        "science discovery breakthrough study findings",
    ],
}


def search_with_expansion(
    user_interests: List[str],
    top_n: int = 10,
    exclude_ids: List[str] = None,
) -> List[Dict]:
    """
    Multi-query retrieval:
    1. HyDE query (main)
    2. Category expansion queries
    3. Sab results merge + deduplicate
    4. Best score by article_id
    5. Threshold + category boost apply
    """
    exclude_ids = exclude_ids or []
    seen: Dict[str, Dict] = {}  # article_id → best result

    fetch_per_query = top_n  # Sirf top_n fetch karo per query — less Pinecone load

    # Query 1: HyDE
    hyde_text = _build_hyde_query(user_interests)
    hyde_results = (
        _search_pinecone(hyde_text, fetch_per_query, exclude_ids)
        if _use_pinecone()
        else _search_chroma(hyde_text, fetch_per_query, exclude_ids)
    )
    for r in hyde_results:
        aid = r["article_id"]
        if aid not in seen or r["score"] > seen[aid]["score"]:
            seen[aid] = r

    # Query 2+: Dynamic expansions — any interest works
    for interest in user_interests:
        expansions = _build_expansion_queries(interest)
        for exp_query in expansions:
            exp_results = (
                _search_pinecone(exp_query, fetch_per_query, exclude_ids)
                if _use_pinecone()
                else _search_chroma(exp_query, fetch_per_query, exclude_ids)
            )
            for r in exp_results:
                aid = r["article_id"]
                if aid not in seen or r["score"] > seen[aid]["score"]:
                    seen[aid] = r

    # Merge → threshold → category boost → sort
    merged = list(seen.values())
    filtered = [r for r in merged if r["score"] >= SIMILARITY_THRESHOLD]

    if user_interests:
        interest_lower = [i.lower() for i in user_interests]
        for r in filtered:
            cat = r.get("category", "").lower()
            if any(cat in i or i in cat for i in interest_lower):
                r["score"] = min(1.0, round(r["score"] + CATEGORY_BOOST, 4))

    filtered.sort(key=lambda x: x["score"], reverse=True)

    logger.info(
        f"search_with_expansion | "
        f"total_fetched={len(seen)} after_threshold={len(filtered)} "
        f"interests={user_interests}"
    )

    return filtered[:top_n]