"""
Demo Seed Script
=================
Creates the admin account, all MongoDB indexes, and a demo matchmaker account.

Run this once after starting MongoDB for the first time:

    cd backend
    python scripts/seed_demo.py

Credentials created
-------------------
  Admin     — username: admin      / password: admin123
  Demo user — username: demo       / password: demo1234

Safe to run multiple times — skips any account that already exists.
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path

_backend_dir = Path(__file__).resolve().parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING, IndexModel

from app.config import get_settings
from app.security import hash_password


# ---------------------------------------------------------------------------
# Index definitions (same as bootstrap.py)
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
    IndexModel([("username", ASCENDING)], name="idx_username", unique=True),
    IndexModel([("email", ASCENDING)], name="idx_email", unique=True, sparse=True),
]

_SUGGESTION_INDEXES = [
    IndexModel([("pair_key", ASCENDING)], name="idx_pair_key", unique=True),
    IndexModel([("candidate_male_id", ASCENDING)], name="idx_candidate_male_id"),
    IndexModel([("candidate_female_id", ASCENDING)], name="idx_candidate_female_id"),
    IndexModel([("status", ASCENDING)], name="idx_status"),
    IndexModel([("created_at", DESCENDING)], name="idx_created_at_desc"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def ensure_indexes(db) -> None:
    await db["candidates"].create_indexes(_CANDIDATE_INDEXES)
    await db["matchmakers"].create_indexes(_MATCHMAKER_INDEXES)
    await db["suggestions"].create_indexes(_SUGGESTION_INDEXES)
    print("  [ok] MongoDB indexes ensured")


async def ensure_user(db, username: str, password: str, display_name: str, role: str, email: str | None = None) -> None:
    existing = await db["matchmakers"].find_one({"username": username})
    if existing:
        print(f"  * '{username}' already exists -- skipping")
        return
    now = datetime.utcnow()
    doc = {
        "username": username,
        "display_name": display_name,
        "email": email,
        "password_hash": hash_password(password),
        "role": role,
        "is_active": True,
        "failed_attempts": 0,
        "locked_until": None,
        "last_login_at": None,
        "created_at": now,
        "updated_at": now,
    }
    result = await db["matchmakers"].insert_one(doc)
    print(f"  [ok] Created '{username}' ({role})  id={result.inserted_id}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def seed() -> None:
    settings = get_settings()
    print(f"Connecting to {settings.mongodb_uri} …")
    client = AsyncIOMotorClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000)

    try:
        await client.admin.command("ping")
        print("  [ok] Connected\n")
    except Exception as exc:
        print(f"  [ERROR] Cannot reach MongoDB: {exc}")
        print("\n  Make sure MongoDB is running:")
        print("    Windows  → net start MongoDB  (if installed as a service)")
        print("    Docker   → docker run -d -p 27017:27017 mongo")
        client.close()
        sys.exit(1)

    db = client[settings.mongodb_db_name]
    print(f"Database: {settings.mongodb_db_name}\n")

    print("Setting up indexes …")
    await ensure_indexes(db)

    print("\nCreating accounts …")
    await ensure_user(db, "admin",  settings.seed_admin_password, "System Administrator", "admin",       "admin@shidduch.local")
    await ensure_user(db, "demo",   "demo1234",                   "Demo Matchmaker",      "matchmaker",  "demo@shidduch.local")

    client.close()
    print("\n[ok] Done!\n")
    print("  Login credentials:")
    print(f"    admin / {settings.seed_admin_password}   (role: admin)")
    print("    demo  / demo1234       (role: matchmaker)")
    print("\n  Start the backend:   cd backend && uvicorn app.main:app --reload")
    print("  Start the frontend:  cd frontend && npm run dev")


if __name__ == "__main__":
    asyncio.run(seed())


