# Article Recommender

A content-based article recommendation system built with FastAPI, HuggingFace embeddings, Pinecone, and Supabase.

## Tech Stack

| Layer | Tool |
|---|---|
| API | FastAPI + Uvicorn |
| Embeddings | HuggingFace `all-MiniLM-L6-v2` |
| Vector DB | Pinecone (production) / ChromaDB (local) |
| Database | Supabase PostgreSQL (production) / SQLite (local) |
| Auth | JWT (python-jose + passlib) |
| Rate Limiting | SlowAPI |
| LLM (optional) | Groq API |
| Package Manager | uv |
| Container | Docker |

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
Dockerfile
docker-compose.yml
```

## Local Development

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

### 4. Download dataset

Download [AG News Classification Dataset](https://www.kaggle.com/datasets/amananandrai/ag-news-classification-dataset) from Kaggle and place `train.csv` in the `data/` directory.

### 5. Ingest articles (local — ChromaDB)

```bash
uv run python -m scripts.ingest --csv data/train.csv --max-rows 30000
```

### 6. Start the server

```bash
uv run uvicorn app.main:app --reload --port 8000
```

API docs: `http://localhost:8000/docs`

## Docker

### Build and run locally

```bash
docker build -t article-recommender .
docker-compose up
```

## Production Setup

### Services required

| Service | Purpose | Free tier |
|---|---|---|
| Supabase | PostgreSQL — users, interactions | 500MB |
| Pinecone | Vector DB — article embeddings | 2GB, 1M RUs |
| Render | API server hosting | 750 hrs/month |

### Ingest to Pinecone (one time)

```bash
# Add PINECONE_API_KEY to .env first
uv run python -m scripts.ingest --csv data/train.csv --max-rows 30000
```

### Deploy to Render

1. Push code to GitHub
2. Create new Web Service on Render
3. Connect GitHub repo
4. Set environment variables
5. Deploy

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
  -d '{"username":"john","email":"john@test.com","password":"secret123","interests":["technology","AI","science"]}'

# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"john","password":"secret123"}'

# Get recommendations
curl http://localhost:8000/api/v1/recommend \
  -H "Authorization: Bearer YOUR_TOKEN"

# Log interaction
curl -X POST http://localhost:8000/api/v1/recommend/interact \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"article_id":"article_42","action":"liked"}'
```

## How It Works

1. **Ingest** — Articles embedded using HuggingFace model, stored in Pinecone (prod) or ChromaDB (local)
2. **Register** — User registers with interests list
3. **Recommend** — Interests embedded → cosine similarity search → top-N articles returned
4. **Interact** — Viewed/liked articles excluded from future recommendations
5. **Groq (optional)** — LLM generates explanation of why articles were recommended

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | ✅ | JWT signing key |
| `DATABASE_URL` | ✅ | PostgreSQL (prod) or SQLite (local) |
| `HF_MODEL_NAME` | ✅ | HuggingFace embedding model |
| `PINECONE_API_KEY` | Production | Pinecone API key |
| `PINECONE_INDEX` | Production | Pinecone index name |
| `TOP_N_RESULTS` | optional | Number of recommendations (default: 10) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | optional | JWT expiry (default: 1440) |
| `RATE_LIMIT_PER_MINUTE` | optional | Rate limit per IP (default: 30) |
| `GROQ_API_KEY` | optional | Groq API key for LLM explanations |
| `GROQ_MODEL` | optional | Groq model (default: llama-3.1-8b-instant) |