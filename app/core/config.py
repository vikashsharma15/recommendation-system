from pydantic import Field
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = Field(default="Article Recommendation", env="APP_NAME")

    database_url: str = Field(
        default="sqlite:///./data/recommender.db", env="DATABASE_URL"
    )

    chroma_persist_dir: str = Field(
        default="./data/chroma", env="CHROMA_PERSIST_DIR"
    )

    hf_model_name: str = Field(
        default="all-MiniLM-L6-v2", env="HF_MODEL_NAME"
    )

    top_n_results: int = Field(default=10, env="TOP_N_RESULTS")

    secret_key: str = Field(..., env="SECRET_KEY")          
    algorithm: str = Field(default="HS256", env="ALGORITHM")
    access_token_expire_minutes: int = Field(
        default=1440, env="ACCESS_TOKEN_EXPIRE_MINUTES"
    )

    rate_limit_per_minute: int = Field(
        default=30, env="RATE_LIMIT_PER_MINUTE"
    )

    groq_api_key: str = Field(default="", env="GROQ_API_KEY")
    groq_model: str = Field(
        default="llama-3.1-8b-instant", env="GROQ_MODEL"
    )

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()