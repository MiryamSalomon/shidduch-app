<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:667eea,50:764ba2,100:f093fb&height=240&section=header&text=✡️%20Shidduch%20App&fontSize=72&fontColor=ffffff&animation=fadeIn&fontAlignY=40&desc=AI-Powered%20Jewish%20Matchmaking%20System&descAlignY=62&descSize=22&descColor=ffffff" width="100%"/>

<br/>

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React_18-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=for-the-badge&logo=typescript&logoColor=white)](https://typescriptlang.org)
[![MongoDB](https://img.shields.io/badge/MongoDB_Atlas-47A248?style=for-the-badge&logo=mongodb&logoColor=white)](https://mongodb.com/atlas)
[![OpenAI](https://img.shields.io/badge/OpenAI_GPT--4o-412991?style=for-the-badge&logo=openai&logoColor=white)](https://openai.com)
[![TailwindCSS](https://img.shields.io/badge/Tailwind_CSS-06B6D4?style=for-the-badge&logo=tailwindcss&logoColor=white)](https://tailwindcss.com)

<br/>

[![Tests](https://img.shields.io/badge/✓%2058%20Tests%20Passing-22c55e?style=for-the-badge)](https://github.com/MiryamSalomon/shidduch-app)
[![i18n](https://img.shields.io/badge/i18n-EN%20%7C%20עברית-6366f1?style=for-the-badge)](https://github.com/MiryamSalomon/shidduch-app)
[![License](https://img.shields.io/badge/License-MIT-f59e0b?style=for-the-badge)](LICENSE)

<br/>

> **A full-stack web platform for Jewish matchmakers (*shadchanim*) to manage candidates,  
> track suggestions, and run AI-powered compatibility scoring — in English and Hebrew.**

</div>

---

## ✨ Features

<table>
<tr>
<td width="50%">

### 🧑‍💼 Candidate Management
- Rich multi-section profiles (personal, education, family, character)
- Dynamic sibling rows with conditional spouse fields
- Soft-delete / archive — data integrity preserved
- Full audit trail (`created_by` / `updated_by`)
- Background embedding generation — zero wait on save

</td>
<td width="50%">

### 🤖 AI Matching Pipeline
- **Step 1** — OpenAI `text-embedding-3-large` (3072-dim) embeds each profile
- **Step 2** — Cosine similarity ranks the best opposite-gender candidates
- **Step 3** — `gpt-4o-mini` scores each pair (0–10) with a bilingual explanation
- **Step 4** — Results upserted preserving any human status updates

</td>
</tr>
<tr>
<td width="50%">

### 💬 Suggestions Workflow
- Proposals created by AI or manually by a matchmaker
- Status lifecycle: `proposed → in_discussion → pending_decision → accepted / rejected`
- Hebrew + English AI explanation on every suggestion card

</td>
<td width="50%">

### 🌐 Internationalisation
- Full EN ↔ **Hebrew** toggle with **live RTL** layout flip
- Language persisted in `localStorage`
- Arrow direction (`←` / `→`) flips automatically per locale
- Zero page reload

</td>
</tr>
<tr>
<td width="50%">

### 🔐 Security
- **Argon2id** password hashing (OWASP #1 recommendation)
- JWT access tokens — HS256, 8-hour expiry
- Rate limiting via `slowapi`
- CORS configured from environment variable
- `.env` never committed

</td>
<td width="50%">

### 🧪 Testing
- **58 passing tests** (pytest-asyncio)
- Covers: auth, full CRUD, filters, pagination, soft-delete, embeddings
- In-memory MongoDB mock — no Atlas needed to run tests
- Mocked OpenAI calls — no API cost for tests

</td>
</tr>
</table>

---

## 🏗️ Architecture

```
shidduch-app/
│
├── backend/                        # Python · FastAPI · Motor
│   ├── app/
│   │   ├── main.py                 # App factory, lifespan, CORS, rate limiting
│   │   ├── security.py             # Argon2id + JWT
│   │   ├── models/                 # Pydantic schemas  (Create · Update · InDB · Out)
│   │   ├── repositories/           # MongoDB queries  (candidate · suggestion · matchmaker)
│   │   ├── routers/                # REST endpoints   (auth · candidates · suggestions · match_run)
│   │   └── services/
│   │       ├── embeddings.py       # Hash-based OpenAI embedding cache
│   │       └── matcher.py          # Full AI pipeline: embed → cosine → GPT rerank → upsert
│   ├── tests/                      # 58 pytest-asyncio tests
│   └── scripts/                    # DB seeding utilities
│
└── frontend/                       # React 18 · TypeScript · Tailwind · Vite
    └── src/
        ├── api/                    # Typed Axios client
        ├── auth/                   # AuthContext + JWT storage
        ├── components/             # Badge · Layout · Pagination · ConfirmDialog · LanguageSwitcher
        ├── i18n/                   # react-i18next config + EN / HE locale files
        └── pages/
            ├── candidates/         # List · Detail · Create / Edit form
            ├── suggestions/        # List · Detail · Create
            ├── admin/              # Matchmakers management
            └── MatchRunPage        # AI match trigger UI
```

---

## 🚀 Getting Started

### Prerequisites

| Tool | Version |
|---|---|
| Python | 3.11+ |
| Node.js | 18+ |
| MongoDB Atlas | Free tier |
| OpenAI API key | Any plan |

### 1 · Backend

```bash
cd backend

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Configure environment
cp .env.example .env
# → Fill in MONGODB_URI, JWT_SECRET, OPENAI_API_KEY

# Start the server
uvicorn app.main:app --reload --port 8000
```

### 2 · Frontend

```bash
cd frontend
npm install
npm run dev
```

App runs at **`http://localhost:5173`** · API at **`http://localhost:8000`**  
Interactive API docs at **`http://localhost:8000/docs`** 📖

### 3 · Seed demo data

```bash
cd backend
python scripts/bootstrap.py     # admin user  →  admin / admin123
python scripts/seed_demo.py     # demo matchmaker  →  demo / demo1234
```

---

## 🧪 Running Tests

```bash
cd backend
pytest -v
```

```
58 passed in 4.12s ✓
```

No Atlas connection required — all tests use an in-memory MongoDB mock.

---

## 📡 API Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/auth/login` | Login → returns JWT |
| `GET` | `/api/v1/candidates` | List with filters & pagination |
| `POST` | `/api/v1/candidates` | Create candidate (auto-embeds in background) |
| `GET` | `/api/v1/candidates/{id}` | Full candidate profile |
| `PATCH` | `/api/v1/candidates/{id}` | Partial update (re-embeds if needed) |
| `DELETE` | `/api/v1/candidates/{id}` | Soft-delete → archived |
| `POST` | `/api/v1/candidates/{id}/embed` | Manual re-embed trigger |
| `POST` | `/api/v1/match-run/{id}` | Run full AI pipeline for a candidate |
| `GET` | `/api/v1/suggestions` | List all suggestions |
| `PATCH` | `/api/v1/suggestions/{id}` | Update suggestion status |
| `GET` | `/health/ready` | Readiness check (pings MongoDB) |

---

## ⚙️ Environment Variables

| Variable | Description |
|---|---|
| `MONGODB_URI` | MongoDB Atlas connection string |
| `JWT_SECRET` | Random secret for signing tokens |
| `OPENAI_API_KEY` | OpenAI API key (embeddings + GPT reranking) |
| `CORS_ORIGINS` | Comma-separated allowed origins |

---

## 💡 Design Decisions

**Argon2id over bcrypt** — Argon2id won the Password Hashing Competition, has no 72-byte truncation limit, and resists both GPU brute-force and side-channel attacks.

**Cosine similarity in Python** — For hundreds of candidates, a Python dot-product loop takes ~1ms. When the dataset scales to thousands, swap for MongoDB Atlas Vector Search (`$vectorSearch` + HNSW index) — the query interface stays identical.

**Background embeddings** — Embedding generation is queued as a FastAPI `BackgroundTask`. The API returns immediately; `has_embeddings` flips to `true` within seconds.

**Hash-based re-embed** — The service computes a SHA-256 hash of the profile text before calling OpenAI. If the hash hasn't changed, the API call is skipped — saving cost on every PATCH that doesn't touch profile fields.

**Soft-delete** — Candidates are archived, never hard-deleted. Suggestions reference candidate IDs — hard deletion would orphan them.

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:f093fb,50:764ba2,100:667eea&height=120&section=footer" width="100%"/>

</div>
