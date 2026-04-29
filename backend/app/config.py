"""
Application Configuration Module
=================================
Loads all environment variables into a single, typed, validated Settings object
using pydantic-settings. This is the **only** place in the codebase that reads
from the environment — every other module imports ``get_settings()`` instead of
calling ``os.getenv()`` directly.

Why pydantic-settings?
    - Validates types at startup (e.g. JWT_EXPIRY_HOURS must be an int).
    - Provides autocomplete and type safety across the codebase.
    - Fails fast with a clear error if a required variable is missing,
      rather than silently using None at runtime.

Usage::

    from app.config import get_settings

    settings = get_settings()
    print(settings.mongodb_uri)
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Typed application settings, populated from environment variables.

    Each field maps to an environment variable of the same name (case-insensitive).
    For example, ``mongodb_uri`` reads from ``MONGODB_URI``.

    Fields are grouped by concern — database, auth, AI, app, rate limiting, and
    seeding — matching the sections in ``.env.example``.
    """

    # ── MongoDB ──────────────────────────────────────────────────────────
    # Full connection string. Use an Atlas SRV URI for production (required
    # for Vector Search); plain ``mongodb://localhost:27017`` works for local
    # CRUD development without vector features.
    mongodb_uri: str = "mongodb://localhost:27017"

    # The database name within the cluster. All collections (candidates,
    # matchmakers, suggestions, audit_log, embedding_cache) live here.
    mongodb_db_name: str = "shidduch"

    # ── Authentication ───────────────────────────────────────────────────
    # Secret key for signing JWT access tokens (HS256). Must be a strong
    # random string in production. Generate one with:
    #   python -c "import secrets; print(secrets.token_hex(32))"
    jwt_secret: str = "CHANGE_ME_TO_A_RANDOM_64_CHAR_HEX_STRING"

    # How long an access token stays valid, in hours.
    # Default 8 = one workday; the matchmaker re-logs in the next morning.
    jwt_expiry_hours: int = 8

    # ── OpenAI ───────────────────────────────────────────────────────────
    # API key from https://platform.openai.com/api-keys
    openai_api_key: str = ""

    # Embedding model name. text-embedding-3-large produces 3072-dim vectors
    # and handles Hebrew reasonably well with bilingual label prefixes.
    openai_embedding_model: str = "text-embedding-3-large"

    # Chat model used by the GPT reranker to score and explain match quality.
    # Use gpt-4o-mini in dev (cheaper) and gpt-4.1 in prod (better reasoning).
    openai_rerank_model: str = "gpt-4o-mini"

    # ── Application ──────────────────────────────────────────────────────
    # Comma-separated list of allowed CORS origins for the frontend.
    # In production, restrict this to the exact frontend domain.
    cors_origins: str = "http://localhost:5173"

    # Structured logging level. One of: DEBUG, INFO, WARNING, ERROR.
    log_level: str = "INFO"

    # ── Rate Limiting ────────────────────────────────────────────────────
    # slowapi rate limit strings. Format: "<count>/<period>".
    rate_limit_login: str = "10/minute"
    rate_limit_match: str = "30/hour"

    # ── Seeding (development only) ───────────────────────────────────────
    # Password assigned to the bootstrap admin matchmaker.
    seed_admin_password: str = "admin123"

    # ── pydantic-settings configuration ──────────────────────────────────
    model_config = SettingsConfigDict(
        # Look for a .env file in the backend/ directory (one level up from app/).
        env_file=".env",
        # If .env is missing, don't crash — fall back to actual env vars or defaults.
        env_file_encoding="utf-8",
        # Ignore extra variables in .env that aren't defined here.
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        """
        Parse the comma-separated CORS_ORIGINS string into a list.

        Returns:
            A list of origin URLs, e.g. ["http://localhost:5173"].
        """
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return a cached, singleton Settings instance.

    Uses ``@lru_cache`` so the .env file is read exactly once, at first call.
    All subsequent calls return the same object — no repeated disk I/O.

    Returns:
        The application Settings object.
    """
    return Settings()
