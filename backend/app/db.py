"""
Database Connection Module
===========================
Manages the async MongoDB connection lifecycle using Motor (the official async
driver for MongoDB built on top of PyMongo).

Architecture decisions:
    - **Single Motor client**: Motor's ``AsyncIOMotorClient`` maintains an
      internal connection pool. We create one instance at app startup and
      reuse it for the entire application lifetime — no per-request overhead.
    - **FastAPI lifespan**: The client is initialised in the lifespan context
      manager (called from ``main.py``) so the connection is established before
      the first request and cleanly closed on shutdown.
    - **Dependency injection**: ``get_db()`` is a FastAPI dependency that
      returns the ``AsyncIOMotorDatabase`` object. Routers declare it as a
      parameter and receive the database handle automatically.

Usage in routers::

    from fastapi import Depends
    from motor.motor_asyncio import AsyncIOMotorDatabase
    from app.db import get_db

    @router.get("/candidates")
    async def list_candidates(db: AsyncIOMotorDatabase = Depends(get_db)):
        cursor = db["candidates"].find({"status": "active"})
        ...

Usage in main.py (lifespan)::

    from app.db import connect_db, close_db

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await connect_db()
        yield
        await close_db()
"""

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import get_settings

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------
# These are set by connect_db() during app startup and cleared by close_db()
# during shutdown. They are module-level (not global mutable singletons)
# because Motor clients are thread-safe and meant to be shared.
_client: AsyncIOMotorClient | None = None
_database: AsyncIOMotorDatabase | None = None


async def connect_db() -> None:
    """
    Initialise the Motor client and select the application database.

    Reads ``MONGODB_URI`` and ``MONGODB_DB_NAME`` from the Settings object.
    Sends a ``ping`` command to verify the connection is alive. If the
    database is unreachable, the ping will raise and the app will fail to
    start — which is the correct behaviour (fail fast, don't serve requests
    without a database).

    This function is idempotent: calling it twice is safe but does nothing
    the second time.

    Raises:
        pymongo.errors.ServerSelectionTimeoutError: If MongoDB is unreachable.
    """
    global _client, _database

    if _client is not None:
        return  # Already connected

    settings = get_settings()

    # Create the async Motor client. Motor manages its own connection pool
    # internally (default pool size = 100 connections).
    _client = AsyncIOMotorClient(settings.mongodb_uri)

    # Select the database by name (e.g. "shidduch").
    _database = _client[settings.mongodb_db_name]

    # Verify connectivity — this will timeout and raise if Mongo is down.
    await _client.admin.command("ping")


async def close_db() -> None:
    """
    Cleanly close the Motor client, releasing all pooled connections.

    Called during FastAPI shutdown. After this, ``get_db()`` will raise
    until ``connect_db()`` is called again.
    """
    global _client, _database

    if _client is not None:
        _client.close()
        _client = None
        _database = None


async def ping_db() -> bool:
    """
    Send a ping command to MongoDB to check if the connection is alive.

    Used by the ``/health/ready`` readiness endpoint. Returns False (rather
    than raising) so the caller can decide how to handle the failure.

    Returns:
        True if MongoDB responded to the ping, False otherwise.
    """
    if _client is None:
        return False
    try:
        await _client.admin.command("ping")
        return True
    except Exception:
        return False


def get_db() -> AsyncIOMotorDatabase:
    """
    FastAPI dependency that returns the current database handle.

    Designed to be used with ``Depends(get_db)`` in route function
    signatures. The returned ``AsyncIOMotorDatabase`` object provides
    access to collections via dict-style lookup: ``db["candidates"]``.

    Returns:
        The ``AsyncIOMotorDatabase`` for the configured database name.

    Raises:
        RuntimeError: If called before ``connect_db()`` has been invoked
            (i.e. the app lifespan has not started yet).
    """
    if _database is None:
        raise RuntimeError(
            "Database not initialised. Ensure connect_db() is called in the "
            "FastAPI lifespan before serving requests."
        )
    return _database
