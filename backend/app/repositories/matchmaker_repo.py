"""
Matchmaker Repository
======================
Data access layer for the ``matchmakers`` collection in MongoDB.

This module contains every database operation related to matchmaker accounts:
creating, reading, updating, listing, and deactivating. No other part of the
codebase talks to ``db["matchmakers"]`` directly — all access goes through
these functions.

Why a separate repository layer?
    - **Single responsibility**: Routers handle HTTP concerns (parsing requests,
      returning responses). Repositories handle database concerns (queries,
      indexes, projections). Neither knows about the other's details.
    - **Testability**: In tests, we can swap the real database with a mock
      without touching router code.
    - **Reusability**: The ``get_by_username`` function is used by both the
      login endpoint (to authenticate) and the create endpoint (to check
      for duplicate usernames). Without a shared repository, that query
      would be duplicated.

All functions are async because Motor (the MongoDB driver) is async.
Each function takes a ``db`` parameter (the Motor database handle) so it
works with FastAPI's dependency injection.
"""

import math
from datetime import datetime

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.matchmaker import MatchmakerInDB


# =============================================================================
# Create
# =============================================================================

async def create_matchmaker(
    db: AsyncIOMotorDatabase,
    data: dict,
) -> MatchmakerInDB:
    """
    Insert a new matchmaker document into the database.

    The ``data`` dict should contain all fields needed for a matchmaker
    document: ``username``, ``display_name``, ``email``, ``password_hash``,
    ``role``. The caller (service or router) is responsible for hashing the
    password before passing it here — the repository never sees plain-text
    passwords.

    Timestamps ``created_at`` and ``updated_at`` are set automatically.

    Args:
        db: The Motor database handle.
        data: A dict of matchmaker fields (password already hashed).

    Returns:
        The newly created matchmaker as a ``MatchmakerInDB`` instance.
    """
    now = datetime.utcnow()
    data["created_at"] = now
    data["updated_at"] = now

    # Set defaults for security fields if not provided.
    data.setdefault("is_active", True)
    data.setdefault("failed_attempts", 0)
    data.setdefault("locked_until", None)
    data.setdefault("last_login_at", None)

    result = await db["matchmakers"].insert_one(data)
    data["_id"] = result.inserted_id

    return MatchmakerInDB(**data)


# =============================================================================
# Read — Single Document
# =============================================================================

async def get_matchmaker_by_id(
    db: AsyncIOMotorDatabase,
    matchmaker_id: str,
) -> MatchmakerInDB | None:
    """
    Find a matchmaker by their MongoDB ObjectId.

    Used by the authentication dependency (``deps.py``) to load the user
    from the JWT's ``sub`` claim, and by admin endpoints to look up
    specific accounts.

    Args:
        db: The Motor database handle.
        matchmaker_id: The matchmaker's ``_id`` as a 24-character hex string.

    Returns:
        The matchmaker document, or None if not found.
    """
    doc = await db["matchmakers"].find_one({"_id": ObjectId(matchmaker_id)})
    if doc is None:
        return None
    return MatchmakerInDB(**doc)


async def get_matchmaker_by_username(
    db: AsyncIOMotorDatabase,
    username: str,
) -> MatchmakerInDB | None:
    """
    Find a matchmaker by their unique username.

    Used during login to look up the account before verifying the password.
    Also used during account creation to check for duplicate usernames.

    Args:
        db: The Motor database handle.
        username: The login username to search for (exact, case-sensitive).

    Returns:
        The matchmaker document, or None if not found.
    """
    doc = await db["matchmakers"].find_one({"username": username})
    if doc is None:
        return None
    return MatchmakerInDB(**doc)


async def get_matchmaker_by_email(
    db: AsyncIOMotorDatabase,
    email: str,
) -> MatchmakerInDB | None:
    """
    Find a matchmaker by their email address.

    Used during account creation to check for duplicate emails.
    Email is optional (some matchmakers may not have one), but if provided
    it must be unique.

    Args:
        db: The Motor database handle.
        email: The email address to search for (exact, case-sensitive).

    Returns:
        The matchmaker document, or None if not found.
    """
    doc = await db["matchmakers"].find_one({"email": email})
    if doc is None:
        return None
    return MatchmakerInDB(**doc)


# =============================================================================
# Read — List (Paginated)
# =============================================================================

async def list_matchmakers(
    db: AsyncIOMotorDatabase,
    *,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """
    List all matchmaker accounts with pagination.

    Returns a dict with ``items``, ``total``, ``page``, ``page_size``,
    and ``total_pages`` — ready to be wrapped in a ``PaginatedResponse``.

    Sorted by creation date (newest first) so recently added accounts
    appear at the top.

    Args:
        db: The Motor database handle.
        page: The page number (1-based).
        page_size: Number of items per page.

    Returns:
        A dict with paginated matchmaker results.
    """
    collection = db["matchmakers"]

    # Count total matching documents for pagination metadata.
    total = await collection.count_documents({})

    # Calculate how many documents to skip for the requested page.
    skip = (page - 1) * page_size

    # Fetch the page of documents, sorted newest first.
    cursor = collection.find({}).sort("created_at", -1).skip(skip).limit(page_size)
    docs = await cursor.to_list(length=page_size)

    items = [MatchmakerInDB(**doc) for doc in docs]
    total_pages = max(1, math.ceil(total / page_size))

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


# =============================================================================
# Update
# =============================================================================

async def update_matchmaker(
    db: AsyncIOMotorDatabase,
    matchmaker_id: str,
    update_data: dict,
) -> MatchmakerInDB | None:
    """
    Partially update a matchmaker document.

    Only the fields present in ``update_data`` are modified; all other
    fields remain unchanged. The ``updated_at`` timestamp is set
    automatically.

    Used by:
        - Admin PATCH endpoint (change role, display name, etc.).
        - Login flow (update ``failed_attempts``, ``locked_until``,
          ``last_login_at``).

    Args:
        db: The Motor database handle.
        matchmaker_id: The matchmaker's ``_id`` as a hex string.
        update_data: A dict of fields to update. Only non-None fields
            should be included.

    Returns:
        The updated matchmaker document, or None if the ID was not found.
    """
    update_data["updated_at"] = datetime.utcnow()

    result = await db["matchmakers"].find_one_and_update(
        {"_id": ObjectId(matchmaker_id)},
        {"$set": update_data},
        # Return the document AFTER the update, not before.
        return_document=True,
    )

    if result is None:
        return None
    return MatchmakerInDB(**result)


# =============================================================================
# Delete (Soft Delete)
# =============================================================================

async def deactivate_matchmaker(
    db: AsyncIOMotorDatabase,
    matchmaker_id: str,
) -> MatchmakerInDB | None:
    """
    Soft-delete a matchmaker by setting ``is_active=False``.

    We never hard-delete matchmaker accounts because:
        1. The audit log references matchmaker IDs — deleting the account
           would orphan those records.
        2. Suggestions and candidates have ``created_by`` / ``updated_by``
           fields that point to matchmaker IDs.
        3. A deactivated account can be reactivated if needed.

    A deactivated account cannot log in (blocked by ``get_current_matchmaker``
    in ``deps.py``).

    Args:
        db: The Motor database handle.
        matchmaker_id: The matchmaker's ``_id`` as a hex string.

    Returns:
        The updated matchmaker document, or None if the ID was not found.
    """
    return await update_matchmaker(
        db,
        matchmaker_id,
        {"is_active": False},
    )
