from pydantic import Field
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # ── App ─────────────────────────────────────────────────
    app_name: str = Field(default="Article Recommender", env="APP_NAME")

    # ── Database ─────────────────────────────────────────────
    database_url: str = Field(
        default="sqlite:///./data/recommender.db", env="DATABASE_URL"
    )

    # ── ChromaDB ─────────────────────────────────────────────
    chroma_persist_dir: str = Field(
        default="./data/chroma", env="CHROMA_PERSIST_DIR"
    )

    # ── HuggingFace ──────────────────────────────────────────
    hf_model_name: str = Field(
        default="all-MiniLM-L6-v2", env="HF_MODEL_NAME"
    )

    # ── Recommendations ──────────────────────────────────────
    top_n_results: int = Field(default=10, env="TOP_N_RESULTS")

    # ── JWT ──────────────────────────────────────────────────
    secret_key: str = Field(..., env="SECRET_KEY")           # required — no default
    algorithm: str = Field(default="HS256", env="ALGORITHM")
    access_token_expire_minutes: int = Field(
        default=1440, env="ACCESS_TOKEN_EXPIRE_MINUTES"      # 24 hours
    )

    # ── Rate Limiting ─────────────────────────────────────────
    rate_limit_per_minute: int = Field(
        default=30, env="RATE_LIMIT_PER_MINUTE"
    )

    # ── Groq (optional) ──────────────────────────────────────
    groq_api_key: str = Field(default="", env="GROQ_API_KEY")
    groq_model: str = Field(
        default="llama-3.1-8b-instant", env="GROQ_MODEL"
    )

    # ── Pinecone ─────────────────────────────────────────────
    pinecone_api_key: str = Field(default="", env="PINECONE_API_KEY")
    pinecone_index: str = Field(default="articles", env="PINECONE_INDEX")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()