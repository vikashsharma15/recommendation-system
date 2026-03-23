from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import get_settings

settings = get_settings()

is_sqlite   = settings.database_url.startswith("sqlite")
is_postgres = settings.database_url.startswith("postgresql")

if is_sqlite:
    # ── Local dev — SQLite ─────────────────────────────────
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
    )

elif is_postgres:
    # ── Production — PostgreSQL / Supabase ─────────────────
    # pool_pre_ping  — har request se pehle connection alive check
    # pool_recycle   — 10 min baad connection refresh (Supabase idle = 5 min)
    # keepalives     — TCP level pe connection alive rakho
    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        pool_recycle=600,
        pool_timeout=30,
        connect_args={
            "connect_timeout": 10,
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 5,
        },
    )

else:
    # Fallback
    engine = create_engine(settings.database_url)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()