"""
Bootstrap Script
=================
Creates the first admin matchmaker account and ensures all required
MongoDB indexes exist.

Run once on first deployment, before starting the application:

    cd backend
    python scripts/bootstrap.py

The admin credentials come from the .env file:
    - Username:  "admin"  (fixed)
    - Password:  SEED_ADMIN_PASSWORD  (set this to something strong in production)

If an admin account already exists, the script exits without making changes.
It is safe to run multiple times.

MongoDB indexes created
-----------------------
candidates:
    - { gender, status, age }  — compound index for filtered list queries
    - { profile_embedding.0 }  — for matching pool queries (has embeddings)
    - { first_name, last_name } — for text search (regex on names)

matchmakers:
    - { username }             — unique, for login lookup
    - { email }                — unique sparse, for uniqueness checks

suggestions:
    - { pair_key }             — unique, prevents duplicate pairs
    - { candidate_male_id }    — for filtering by candidate
    - { candidate_female_id }  — for filtering by candidate
    - { status }               — for filtering by status
    - { created_at }           — for chronological sorting
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path

# Make sure the backend package is importable when running from project root
# or from the backend/ directory.
_backend_dir = Path(__file__).resolve().parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING, IndexModel

from app.config import get_settings
from app.security import hash_password


# ---------------------------------------------------------------------------
# Index definitions
# ---------------------------------------------------------------------------

_CANDIDATE_INDEXES = [
    IndexModel(
        [("gender", ASCENDING), ("status", ASCENDING), ("age", ASCENDING)],
        name="idx_gender_status_age",
    ),
    IndexModel(
        [("profile_embedding.0", ASCENDING)],
        name="idx_has_profile_embedding",
        sparse=True,
    ),
    IndexModel(
        [("first_name", ASCENDING), ("last_name", ASCENDING)],
        name="idx_name",
    ),
    IndexModel(
        [("created_at", DESCENDING)],
        name="idx_created_at_desc",
    ),
]

_MATCHMAKER_INDEXES = [
    IndexModel(
        [("username", ASCENDING)],
        name="idx_username",
        unique=True,
    ),
    IndexModel(
        [("email", ASCENDING)],
        name="idx_email",
        unique=True,
        sparse=True,  # Sparse so that null emails don't conflict.
    ),
]

_SUGGESTION_INDEXES = [
    IndexModel(
        [("pair_key", ASCENDING)],
        name="idx_pair_key",
        unique=True,
    ),
    IndexModel(
        [("candidate_male_id", ASCENDING)],
        name="idx_candidate_male_id",
    ),
    IndexModel(
        [("candidate_female_id", ASCENDING)],
        name="idx_candidate_female_id",
    ),
    IndexModel(
        [("status", ASCENDING)],
        name="idx_status",
    ),
    IndexModel(
        [("created_at", DESCENDING)],
        name="idx_created_at_desc",
    ),
]


# ---------------------------------------------------------------------------
# Bootstrap logic
# ---------------------------------------------------------------------------

async def create_indexes(db) -> None:
    print("Creating MongoDB indexes...")
    await db["candidates"].create_indexes(_CANDIDATE_INDEXES)
    print("  ✓ candidates indexes")
    await db["matchmakers"].create_indexes(_MATCHMAKER_INDEXES)
    print("  ✓ matchmakers indexes")
    await db["suggestions"].create_indexes(_SUGGESTION_INDEXES)
    print("  ✓ suggestions indexes")


async def create_admin(db, settings) -> None:
    existing = await db["matchmakers"].find_one({"role": "admin"})
    if existing:
        print(f"\nAdmin account already exists: '{existing['username']}' — skipping creation.")
        return

    now = datetime.utcnow()
    admin_doc = {
        "username": "admin",
        "display_name": "System Administrator",
        "email": None,
        "password_hash": hash_password(settings.seed_admin_password),
        "role": "admin",
        "is_active": True,
        "failed_attempts": 0,
        "locked_until": None,
        "last_login_at": None,
        "created_at": now,
        "updated_at": now,
    }

    result = await db["matchmakers"].insert_one(admin_doc)
    print(f"\nAdmin matchmaker created.")
    print(f"  ID:       {result.inserted_id}")
    print(f"  Username: admin")
    print(f"  Password: {settings.seed_admin_password}")
    print("\n  IMPORTANT: Change the password immediately after first login!")


async def bootstrap() -> None:
    settings = get_settings()

    print(f"Connecting to MongoDB at {settings.mongodb_uri}...")
    client = AsyncIOMotorClient(settings.mongodb_uri)

    try:
        await client.admin.command("ping")
        print("  ✓ Connected")
    except Exception as exc:
        print(f"  ✗ Failed to connect: {exc}")
        client.close()
        sys.exit(1)

    db = client[settings.mongodb_db_name]
    print(f"  Database: {settings.mongodb_db_name}\n")

    await create_indexes(db)
    await create_admin(db, settings)

    client.close()
    print("\nBootstrap complete.")


if __name__ == "__main__":
    asyncio.run(bootstrap())
