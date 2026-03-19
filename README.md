# Article Recommender

A production-ready content-based article recommendation API built with FastAPI, HuggingFace sentence embeddings, Pinecone vector search, and Supabase PostgreSQL.

## Architecture

```
Client
  └── FastAPI (Render / Docker)
        ├── Auth → JWT (python-jose + bcrypt)
        ├── Rate Limiting → SlowAPI
        ├── Recommendations
        │     ├── Embed interests → HuggingFace all-MiniLM-L6-v2
        │     └── Vector search → Pinecone (prod) / ChromaDB (local)
        └── User data → Supabase PostgreSQL (prod) / SQLite (local)
```

## Tech Stack

| Layer | Local | Production |
|---|---|---|
| API | FastAPI + Uvicorn | FastAPI + Uvicorn |
| Embeddings | all-MiniLM-L6-v2 (HuggingFace) | all-MiniLM-L6-v2 (HuggingFace) |
| Vector DB | ChromaDB (local file) | Pinecone (cloud) |
| Database | SQLite | Supabase PostgreSQL |
| Container | Docker Compose | Docker (Render) |
| Auth | JWT | JWT |
| Rate Limiting | SlowAPI | SlowAPI |
| LLM (optional) | Groq API | Groq API |
| Package Manager | uv | uv |

## Project Structure

```
article-recommender/
├── app/
│   ├── api/
│   │   ├── router.py            # registers all v1 routers
│   │   └── v1/
│   │       ├── auth.py          # register, login
│   │       ├── users.py         # profile, preferences
│   │       ├── recommend.py     # recommendations, interactions
│   │       └── articles.py      # index status
│   ├── core/
│   │   └── config.py            # env-based settings
│   ├── db/
│   │   ├── base.py              # SQLAlchemy base
│   │   ├── session.py           # engine, get_db
│   │   └── models/
│   │       ├── user.py
│   │       └── interaction.py
│   ├── middleware/
│   │   ├── auth.py              # JWT + bcrypt
│   │   └── rate_limit.py        # SlowAPI limiter
│   ├── schemas/
│   │   ├── auth.py
│   │   ├── user.py
│   │   ├── recommend.py
│   │   └── common.py
│   ├── services/
│   │   ├── embedding.py         # HF model + Pinecone/ChromaDB
│   │   ├── recommendation.py    # core rec logic
│   │   └── groq.py              # optional LLM explanation
│   └── main.py
├── scripts/
│   └── ingest.py                # dataset → vector DB
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── .env.example
```

## Local Development

### Prerequisites
- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- Docker (optional)

### 1. Clone

```bash
git clone https://github.com/vikashsharma15/recommendation-system.git
cd recommendation-system
```

### 2. Install dependencies

```bash
uv sync
```

### 3. Configure environment

```bash
cp .env.example .env
```

Generate secret key:

```bash
uv run python -c "import secrets; print(secrets.token_hex(32))"
```

Minimum required in `.env`:
```env
SECRET_KEY=your-generated-key
DATABASE_URL=sqlite:///./data/recommender.db
```

### 4. Download dataset

Download [AG News Classification Dataset](https://www.kaggle.com/datasets/amananandrai/ag-news-classification-dataset) → place `train.csv` in `data/`.

### 5. Ingest articles

```bash
uv run python -m scripts.ingest --csv data/train.csv --max-rows 30000
```

### 6. Run server

```bash
uv run uvicorn app.main:app --reload --port 8000
```

Swagger UI: `http://localhost:8000/docs`

## Docker (local)

```bash
docker compose up --build
```

## Production Setup

### Required services (all free tier)

| Service | Purpose | Link |
|---|---|---|
| Supabase | PostgreSQL — users, interactions | [supabase.com](https://supabase.com) |
| Pinecone | Vector DB — article embeddings | [pinecone.io](https://pinecone.io) |
| Render | API server hosting | [render.com](https://render.com) |

### One-time Pinecone ingest

```bash
# Set PINECONE_API_KEY in .env first
uv run python -m scripts.ingest --csv data/train.csv --max-rows 30000
```

### Deploy to Render

1. Push to GitHub
2. Render → New Web Service → connect repo
3. Set environment variables (see table below)
4. Deploy — Render uses `Dockerfile` automatically

## API Endpoints

### Auth
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/auth/register` | Register with interests |
| POST | `/api/v1/auth/login` | Login → JWT token |

### Users
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/api/v1/users/me` | ✅ | Get own profile |
| PUT | `/api/v1/users/me/preferences` | ✅ | Update interests |

### Recommendations
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/api/v1/recommend` | ✅ | Get top-N articles |
| POST | `/api/v1/recommend/interact` | ✅ | Log viewed/liked/skipped |

### Other
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/articles/status` | Articles indexed count |
| GET | `/api/v1/health` | Health check |

## Quick Start

```bash
# 1. Register
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"john","email":"john@test.com","password":"secret123","interests":["technology","AI","science"]}'

# 2. Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"john","password":"secret123"}'

# 3. Get recommendations (use token from login)
curl http://localhost:8000/api/v1/recommend \
  -H "Authorization: Bearer YOUR_TOKEN"

# 4. Log interaction
curl -X POST http://localhost:8000/api/v1/recommend/interact \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"article_id":"article_42","action":"liked"}'
```

## How It Works

1. **Ingest** — Articles embedded via HuggingFace, stored in Pinecone (prod) or ChromaDB (local)
2. **Register** — User registers with interest keywords
3. **Recommend** — Interests embedded → cosine similarity → top-N matching articles
4. **Interact** — Viewed/liked articles excluded from future recommendations
5. **Groq** — Optional LLM explains why articles were recommended

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `SECRET_KEY` | ✅ | — | JWT signing key |
| `DATABASE_URL` | ✅ | SQLite | PostgreSQL or SQLite URL |
| `HF_MODEL_NAME` | ✅ | `all-MiniLM-L6-v2` | Embedding model |
| `PINECONE_API_KEY` | Production | — | Pinecone API key |
| `PINECONE_INDEX` | Production | `articles` | Pinecone index name |
| `TOP_N_RESULTS` | — | `10` | Recommendations count |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | — | `1440` | JWT expiry |
| `RATE_LIMIT_PER_MINUTE` | — | `30` | Rate limit per IP |
| `GROQ_API_KEY` | — | — | Groq key (optional) |
| `GROQ_MODEL` | — | `llama-3.1-8b-instant` | Groq model |
