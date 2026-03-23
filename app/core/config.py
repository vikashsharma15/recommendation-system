from pydantic import Field
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # ── App ──────────────────────────────────────────────────
    app_name: str = Field(default="Recomr", env="APP_NAME")

    # ── Database ─────────────────────────────────────────────
    database_url: str = Field(default="sqlite:///./data/recomr.db", env="DATABASE_URL")
    chroma_persist_dir: str = Field(default="./data/chroma", env="CHROMA_PERSIST_DIR")

    # ── HuggingFace ──────────────────────────────────────────
    hf_model_name: str = Field(default="all-MiniLM-L6-v2", env="HF_MODEL_NAME")

    # ── Pinecone ─────────────────────────────────────────────
    pinecone_api_key: str = Field(default="", env="PINECONE_API_KEY")
    pinecone_index:   str = Field(default="articles", env="PINECONE_INDEX")
    use_pinecone:    bool = Field(default=True, env="USE_PINECONE")

    # ── Redis ─────────────────────────────────────────────────
    upstash_redis_rest_url:   str = Field(default="", env="UPSTASH_REDIS_REST_URL")
    upstash_redis_rest_token: str = Field(default="", env="UPSTASH_REDIS_REST_TOKEN")
    cache_ttl_seconds:        int = Field(default=300, env="CACHE_TTL_SECONDS")

    # ── JWT ──────────────────────────────────────────────────
    secret_key: str = Field(..., env="SECRET_KEY")
    algorithm:  str = Field(default="HS256", env="ALGORITHM")
    access_token_expire_minutes:  int = Field(default=30,    env="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_minutes: int = Field(default=10080, env="REFRESH_TOKEN_EXPIRE_MINUTES")

    # ── Rate limiting ─────────────────────────────────────────
    rate_limit_per_minute: int = Field(default=30, env="RATE_LIMIT_PER_MINUTE")

    # ── Groq ─────────────────────────────────────────────────
    groq_api_key: str = Field(default="", env="GROQ_API_KEY")
    groq_model:   str = Field(default="llama-3.1-8b-instant", env="GROQ_MODEL")

    # ── Pagination ────────────────────────────────────────────
    default_page_size: int = Field(default=10, env="DEFAULT_PAGE_SIZE")
    max_page_size:     int = Field(default=50, env="MAX_PAGE_SIZE")
    top_n_results:     int = Field(default=50, env="TOP_N_RESULTS")

    # ── Search tuning (.env se aata hai) ──────────────────────
    embed_batch_size:     int   = Field(default=256,  env="EMBED_BATCH_SIZE")
    chroma_batch_size:    int   = Field(default=5000, env="CHROMA_BATCH_SIZE")
    similarity_threshold: float = Field(default=0.28, env="SIMILARITY_THRESHOLD")
    retrieve_multiplier:  int   = Field(default=2,    env="RETRIEVE_MULTIPLIER")
    category_boost:       float = Field(default=0.08, env="CATEGORY_BOOST")

    # ── Username change policy ────────────────────────────────
    username_change_limit_per_month: int = Field(default=2, env="USERNAME_CHANGE_LIMIT")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()