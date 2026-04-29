"""
FastAPI Application Factory
=============================
Creates and configures the FastAPI application instance.

This is the entry point for the backend. It handles:
    - **Lifespan management**: Connects to MongoDB on startup, disconnects
      on shutdown (via the async context manager pattern).
    - **CORS**: Configured from ``CORS_ORIGINS`` env var so the React
      frontend can make cross-origin requests.
    - **Router registration**: All API routers are mounted under ``/api/v1``.
    - **Health check**: A simple ``/health`` endpoint for uptime monitoring
      and container health checks.

Usage (development)::

    uvicorn app.main:app --reload --port 8000

Usage (production)::

    uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import get_settings
from app.db import close_db, connect_db, ping_db
from app.limiter import limiter
from app.routers import auth, candidates, match_run, matchmakers, suggestions


# ---------------------------------------------------------------------------
# Lifespan — runs once on startup and once on shutdown
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifecycle events.

    **Startup** (before ``yield``):
        - Connect to MongoDB and verify the connection is alive.

    **Shutdown** (after ``yield``):
        - Close the MongoDB connection pool cleanly.

    This pattern replaces the deprecated ``@app.on_event("startup")`` /
    ``@app.on_event("shutdown")`` hooks and is the recommended approach
    in FastAPI ≥0.95.
    """
    await connect_db()
    yield
    await close_db()


# ---------------------------------------------------------------------------
# Application instance
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Shidduch Matchmaking API",
    description=(
        "Backend API for the Shidduch matchmaking system. "
        "Manages candidates, matchmakers, AI-powered match suggestions, "
        "and the full suggestion lifecycle."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Attach the rate limiter to the app and register its 429 error handler.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    # Which origins (frontend URLs) are allowed to make requests.
    allow_origins=settings.cors_origins_list,
    # Allow the browser to send cookies / Authorization headers.
    allow_credentials=True,
    # Allow all HTTP methods (GET, POST, PATCH, DELETE, OPTIONS).
    allow_methods=["*"],
    # Allow all headers (including Authorization for JWT).
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Router Registration
# ---------------------------------------------------------------------------
# All routers are mounted under /api/v1 for versioning. When v2 is needed,
# add a new set of routers under /api/v2 without breaking existing clients.

app.include_router(auth.router, prefix="/api/v1")
app.include_router(matchmakers.router, prefix="/api/v1")
app.include_router(candidates.router, prefix="/api/v1")
app.include_router(suggestions.router, prefix="/api/v1")
app.include_router(match_run.router, prefix="/api/v1")


# ---------------------------------------------------------------------------
# Health Check
# ---------------------------------------------------------------------------

@app.get(
    "/health",
    tags=["Operations"],
    summary="Liveness check — is the server process alive?",
)
async def health_check():
    """
    Liveness check. Returns ``{"status": "ok"}`` if the server process is
    running. Does NOT verify the database connection.

    Use ``/health/ready`` for a full readiness check before routing traffic.
    """
    return {"status": "ok"}


@app.get(
    "/health/ready",
    tags=["Operations"],
    summary="Readiness check — is the server ready to serve traffic?",
    responses={
        200: {"description": "Server is ready"},
        503: {"description": "Database is unreachable"},
    },
)
async def health_ready():
    """
    Readiness check. Pings MongoDB and returns ``{"status": "ready"}`` if
    the connection is alive, or HTTP 503 if MongoDB is unreachable.

    Used by Docker ``HEALTHCHECK``, Kubernetes readiness probes, and load
    balancers to determine when the container should receive traffic.
    Unlike the liveness endpoint, a 503 here means "temporarily remove from
    rotation" rather than "restart the container".
    """
    if not await ping_db():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unreachable.",
        )
    return {"status": "ready"}
