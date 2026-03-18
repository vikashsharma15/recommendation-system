# Article Recommender

A content-based article recommendation system built with FastAPI, HuggingFace embeddings, and ChromaDB.

## Tech Stack

| Layer | Tool |
|---|---|
| API | FastAPI + Uvicorn |
| Embeddings | HuggingFace `all-MiniLM-L6-v2` |
| Vector DB | ChromaDB (local, persistent) |
| Database | SQLite via SQLAlchemy |
| Auth | JWT (python-jose + passlib) |
| Rate Limiting | SlowAPI |
| LLM (optional) | Groq API |
| Package Manager | uv |

## Project Structure

```
app/
├── api/
│   ├── router.py
│   └── v1/
│       ├── auth.py
│       ├── users.py
│       ├── recommend.py
│       └── articles.py
├── core/
│   └── config.py
├── db/
│   ├── base.py
│   ├── session.py
│   └── models/
│       ├── user.py
│       └── interaction.py
├── middleware/
│   ├── auth.py
│   └── rate_limit.py
├── schemas/
│   ├── auth.py
│   ├── user.py
│   ├── recommend.py
│   └── common.py
├── services/
│   ├── embedding.py
│   ├── recommendation.py
│   └── groq.py
└── main.py
scripts/
└── ingest.py
```

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/article-recommender.git
cd article-recommender
```

### 2. Install dependencies

```bash
uv sync
```

### 3. Configure environment

```bash
cp .env.example .env
```

Generate a secret key:

```bash
uv run python -c "import secrets; print(secrets.token_hex(32))"
```

Update `.env`:

```env
SECRET_KEY=your-generated-secret-key
GROQ_API_KEY=your-groq-api-key        # optional
```

### 4. Download dataset

Download [AG News Classification Dataset](https://www.kaggle.com/datasets/amananandrai/ag-news-classification-dataset) from Kaggle and place `train.csv` in the `data/` directory.

### 5. Ingest articles

```bash
uv run python -m scripts.ingest --csv data/train.csv --max-rows 30000
```

### 6. Start the server

```bash
uv run uvicorn app.main:app --reload --port 8000
```

API docs available at `http://localhost:8000/docs`

## API Endpoints

### Auth
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/auth/register` | Register new user |
| POST | `/api/v1/auth/login` | Login, get JWT token |

### Users
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/users/me` | Get own profile |
| PUT | `/api/v1/users/me/preferences` | Update interests |

### Recommendations
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/recommend` | Get top-N recommendations |
| POST | `/api/v1/recommend/interact` | Log viewed/liked/skipped |

### Articles
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/articles/status` | Check indexed article count |

### Health
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/health` | Health check |

## Usage Example

```bash
# Register
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"john","email":"john@example.com","password":"secret123","interests":["technology","AI","machine learning"]}'

# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"john","password":"secret123"}'

# Get recommendations (use token from login response)
curl http://localhost:8000/api/v1/recommend \
  -H "Authorization: Bearer YOUR_TOKEN"

# Log interaction
curl -X POST http://localhost:8000/api/v1/recommend/interact \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"article_id":"article_42","action":"liked"}'
```

## How It Works

1. **Ingest** — Articles from CSV are embedded using HuggingFace model and stored in ChromaDB
2. **Register** — User registers with a list of interests
3. **Recommend** — User interests are embedded and compared against article vectors using cosine similarity
4. **Interact** — Viewed/liked articles are excluded from future recommendations
5. **Groq (optional)** — Generates a natural language explanation of why articles were recommended

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | required | JWT signing key |
| `DATABASE_URL` | `sqlite:///./data/recommender.db` | SQLite path |
| `CHROMA_PERSIST_DIR` | `./data/chroma` | ChromaDB storage path |
| `HF_MODEL_NAME` | `all-MiniLM-L6-v2` | HuggingFace embedding model |
| `TOP_N_RESULTS` | `10` | Number of recommendations |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | JWT expiry (24 hours) |
| `RATE_LIMIT_PER_MINUTE` | `30` | Rate limit per IP |
| `GROQ_API_KEY` | empty | Groq API key (optional) |
| `GROQ_MODEL` | `llama-3.1-8b-instant` | Groq model name |
