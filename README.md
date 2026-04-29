# Shidduch Matchmaking System

A full-stack web application for Jewish matchmakers (*shadchanim*) to manage candidates, track match suggestions, and run AI-powered compatibility scoring.

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python · FastAPI · Motor (async MongoDB) · MongoDB Atlas |
| **Frontend** | React 18 · TypeScript · Tailwind CSS · Vite |
| **AI / ML** | OpenAI Embeddings (`text-embedding-3-large`) · GPT-4o-mini reranking |
| **Auth** | JWT (HS256) · Argon2id password hashing |
| **Testing** | pytest-asyncio · 58 passing tests |
| **i18n** | react-i18next · English & Hebrew with live RTL switching |

---

## Features

### Candidate Management
- Full CRUD with rich form validation (React Hook Form + Zod)
- Detailed profiles: personal info, education, family background, character traits, preferences
- Dynamic sibling rows with conditional spouse fields
- Soft-delete (archive) — candidates are never hard-deleted because suggestions reference their IDs
- Audit trail: `created_by` / `updated_by` on every write

### AI Matching Pipeline
1. **Embedding** — Each candidate's profile and preferences are embedded with `text-embedding-3-large` (3072-dim vectors) and stored in MongoDB
2. **Vector Search** — Cosine similarity between a candidate's `preferences_embedding` and every opposite-gender candidate's `profile_embedding`
3. **GPT Reranking** — Top N pairs are scored (0–10) and explained in Hebrew + English by `gpt-4o-mini`
4. **Upsert** — Results are stored preserving any human status updates on existing suggestions

### Suggestions Workflow
- Proposals created by AI or manually by a matchmaker
- Status lifecycle: `proposed → in_discussion → pending_decision → accepted / rejected`
- Bilingual AI explanation (Hebrew + English) displayed on each suggestion

### Internationalisation
- Full EN ↔ Hebrew toggle with live RTL layout flip (no page reload)
- Language persisted in `localStorage`
- Arrow direction (`←` / `→`) flips automatically per locale

### Security
- Argon2id password hashing (OWASP recommended, no 72-byte truncation limit)
- JWT access tokens (8-hour expiry, no refresh tokens in v1)
- Rate limiting via slowapi
- CORS configured from environment variable
- `.env` never committed — `.env.example` provided

---

## Project Structure

```
shidduch-app/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app factory, lifespan, CORS
│   │   ├── config.py            # Pydantic settings (env vars)
│   │   ├── security.py          # Argon2id + JWT
│   │   ├── deps.py              # FastAPI dependency injection
│   │   ├── db.py                # Motor connection pool
│   │   ├── limiter.py           # slowapi rate limiter
│   │   ├── models/              # Pydantic schemas (In/Out/DB)
│   │   ├── repositories/        # DB queries (candidate, suggestion, matchmaker)
│   │   ├── routers/             # API endpoints
│   │   └── services/
│   │       ├── embeddings.py    # OpenAI embedding generation + hash-based caching
│   │       └── matcher.py       # Full AI matching pipeline
│   ├── tests/                   # 58 pytest-asyncio tests
│   └── scripts/                 # DB seeding utilities
└── frontend/
    └── src/
        ├── api/                 # Typed API client (axios)
        ├── auth/                # AuthContext + JWT storage
        ├── components/          # Badge, Layout, Pagination, ConfirmDialog
        ├── i18n/                # react-i18next config + EN/HE locale files
        ├── pages/
        │   ├── candidates/      # List · Detail · Create/Edit form
        │   ├── suggestions/     # List · Detail · Create
        │   ├── admin/           # Matchmakers management
        │   └── MatchRunPage     # AI match trigger UI
        └── types/               # Shared TypeScript types
```

---

## Getting Started

### Prerequisites
- Python 3.11+
- Node.js 18+
- MongoDB Atlas cluster (free tier works)
- OpenAI API key

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

cp .env.example .env
# Fill in MONGODB_URI, JWT_SECRET, OPENAI_API_KEY in .env

uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The app opens at `http://localhost:5173`. The backend API is at `http://localhost:8000`.

### Seed demo data

```bash
cd backend
python scripts/bootstrap.py   # creates admin user (admin / admin123)
python scripts/seed_demo.py   # adds demo matchmaker (demo / demo1234)
```

---

## Running Tests

```bash
cd backend
pytest -v
# 58 tests, all passing
```

Tests use an in-memory MongoDB mock — no Atlas connection required.

---

## API Highlights

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/auth/login` | Login → JWT |
| `GET` | `/api/v1/candidates` | List with filters & pagination |
| `POST` | `/api/v1/candidates` | Create candidate (embeds in background) |
| `PATCH` | `/api/v1/candidates/{id}` | Partial update |
| `POST` | `/api/v1/candidates/{id}/embed` | Manual re-embed trigger |
| `POST` | `/api/v1/match-run/{id}` | Run AI matching for a candidate |
| `GET` | `/api/v1/suggestions` | List suggestions |
| `PATCH` | `/api/v1/suggestions/{id}` | Update suggestion status |

Interactive docs: `http://localhost:8000/docs`

---

## Environment Variables

Copy `backend/.env.example` and fill in:

| Variable | Description |
|---|---|
| `MONGODB_URI` | MongoDB Atlas connection string |
| `JWT_SECRET` | Random secret for signing JWTs |
| `OPENAI_API_KEY` | OpenAI API key (embeddings + GPT reranking) |
| `CORS_ORIGINS` | Comma-separated allowed origins (e.g. `http://localhost:5173`) |

---

## Architecture Notes

**Why cosine similarity in Python?**
For hundreds of candidates a Python dot-product loop is fast enough (~1ms). When the dataset grows to thousands, replace with MongoDB Atlas Vector Search (`$vectorSearch` + HNSW index) — the query interface stays identical.

**Why no refresh tokens in v1?**
An 8-hour access token covers a matchmaker's workday. Refresh token rotation adds complexity (storage, revocation, rotation race conditions) not justified for a small team.

**Why Argon2id over bcrypt?**
Argon2id won the Password Hashing Competition, has no 72-byte truncation limit, and resists both GPU brute-force and side-channel attacks.
