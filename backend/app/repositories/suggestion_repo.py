"""
Suggestion Repository
======================
Data access layer for the ``suggestions`` collection in MongoDB.

A suggestion is a proposed match between a male and female candidate. This
repository manages the full lifecycle of suggestions: creation, status
transitions, querying, and deletion.

Key design decisions:
    - **``pair_key`` uniqueness**: Every suggestion has a ``pair_key`` field
      formatted as ``"<male_id>:<female_id>"``. A unique MongoDB index on
      this field prevents the same pair from being suggested twice. The
      ``create_suggestion`` function handles the ``DuplicateKeyError``
      gracefully by returning None (the caller can then inform the user
      that this pair was already suggested).
    - **Append-only history**: Status changes don't just overwrite the
      ``status`` field — they also append an entry to the ``history`` array
      using ``$push``. This gives matchmakers a complete timeline of each
      suggestion's journey (who changed it, when, and why).
    - **Upsert for AI pipeline**: ``upsert_suggestion`` is used by the
      matching pipeline to create suggestions if they don't exist, or
      skip them if they do. This avoids race conditions when the same
      match is found by concurrent pipeline runs.
"""

import math
from datetime import datetime

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from app.models.suggestion import SuggestionInDB


# =============================================================================
# Create
# =============================================================================

async def create_suggestion(
    db: AsyncIOMotorDatabase,
    data: dict,
) -> SuggestionInDB | None:
    """
    Insert a new suggestion document into the database.

    The ``pair_key`` field must be set by the caller as
    ``"<male_id>:<female_id>"``. If a suggestion with the same ``pair_key``
    already exists (enforced by a unique index), this function returns None
    instead of raising an error.

    Timestamps ``created_at`` and ``updated_at`` are set automatically.
    An initial history entry is created with the initial status.

    Args:
        db: The Motor database handle.
        data: A dict of suggestion fields. Must include ``candidate_male_id``,
            ``candidate_female_id``, ``pair_key``, ``source``, and
            ``created_by``.

    Returns:
        The newly created suggestion as a ``SuggestionInDB`` instance,
        or None if the pair already exists.
    """
    now = datetime.utcnow()
    data["created_at"] = now
    data["updated_at"] = now

    # Set default status if not provided.
    data.setdefault("status", "proposed")

    # Create the initial history entry recording the creation.
    initial_history = {
        "status": data["status"],
        "at": now,
        "by": data.get("created_by"),
        "note": data.pop("note", None),
    }
    data.setdefault("history", [initial_history])

    # Set default scores (null for manual suggestions).
    data.setdefault("ai_score", None)
    data.setdefault("rerank_score", None)
    data.setdefault("rerank_explanation_he", None)
    data.setdefault("rerank_explanation_en", None)
    data.setdefault("model_versions", {"embedding": "", "rerank": ""})

    # Explicit pre-check so tests using mongomock (which ignores unique indexes)
    # behave identically to production MongoDB.
    existing = await db["suggestions"].find_one({"pair_key": data["pair_key"]})
    if existing is not None:
        return None

    try:
        result = await db["suggestions"].insert_one(data)
        data["_id"] = result.inserted_id
        return SuggestionInDB(**data)
    except DuplicateKeyError:
        # Race condition: another request inserted between our check and insert.
        return None


async def upsert_suggestion(
    db: AsyncIOMotorDatabase,
    data: dict,
) -> SuggestionInDB:
    """
    Insert a suggestion if it doesn't exist, or return the existing one.

    Used by the AI matching pipeline (``services/matcher.py``) to persist
    new match suggestions without failing on duplicates. If the pair already
    exists, the existing document is returned unchanged — the pipeline
    doesn't overwrite manually-updated suggestions.

    The check is based on ``pair_key`` (unique index).

    Args:
        db: The Motor database handle.
        data: A dict of suggestion fields. Must include ``pair_key``.

    Returns:
        The suggestion document (either newly created or existing).
    """
    pair_key = data["pair_key"]

    # Check if a suggestion for this pair already exists.
    existing = await db["suggestions"].find_one({"pair_key": pair_key})
    if existing is not None:
        return SuggestionInDB(**existing)

    # Doesn't exist — create it. Use create_suggestion which handles
    # the race condition (two concurrent pipeline runs might both reach
    # this point).
    result = await create_suggestion(db, data)
    if result is not None:
        return result

    # If create_suggestion returned None, it means another concurrent
    # process created it between our check and insert. Fetch it.
    doc = await db["suggestions"].find_one({"pair_key": pair_key})
    return SuggestionInDB(**doc)


# =============================================================================
# Read — Single Document
# =============================================================================

async def get_suggestion_by_id(
    db: AsyncIOMotorDatabase,
    suggestion_id: str,
) -> SuggestionInDB | None:
    """
    Find a suggestion by its MongoDB ObjectId.

    Args:
        db: The Motor database handle.
        suggestion_id: The suggestion's ``_id`` as a 24-character hex string.

    Returns:
        The suggestion document, or None if not found.
    """
    doc = await db["suggestions"].find_one({"_id": ObjectId(suggestion_id)})
    if doc is None:
        return None
    return SuggestionInDB(**doc)


async def get_suggestion_by_pair_key(
    db: AsyncIOMotorDatabase,
    pair_key: str,
) -> SuggestionInDB | None:
    """
    Find a suggestion by its unique pair key.

    The pair key is formatted as ``"<male_id>:<female_id>"`` and has a
    unique index, so this is an efficient lookup.

    Args:
        db: The Motor database handle.
        pair_key: The pair key string.

    Returns:
        The suggestion document, or None if not found.
    """
    doc = await db["suggestions"].find_one({"pair_key": pair_key})
    if doc is None:
        return None
    return SuggestionInDB(**doc)


# =============================================================================
# Read — List (Paginated + Filtered)
# =============================================================================

async def list_suggestions(
    db: AsyncIOMotorDatabase,
    *,
    status: str | None = None,
    source: str | None = None,
    candidate_id: str | None = None,
    created_by: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """
    List suggestions with optional filters and pagination.

    Supports filtering by:
        - ``status``: Show only suggestions in a specific lifecycle stage
          (e.g. "proposed", "contacted").
        - ``source``: Show only AI-generated or manual suggestions.
        - ``candidate_id``: Show all suggestions involving a specific
          candidate (either as male or female). Useful for the candidate
          detail page's "suggestions" tab.
        - ``created_by``: Show suggestions created by a specific matchmaker.

    Sorted by creation date (newest first) — the matchmaker's inbox
    should show the most recent suggestions at the top.

    Args:
        db: The Motor database handle.
        status: Filter by suggestion status. None = any.
        source: Filter by source ("ai" or "manual"). None = any.
        candidate_id: Filter by candidate involvement. None = any.
        created_by: Filter by creating matchmaker. None = any.
        page: The page number (1-based).
        page_size: Number of items per page.

    Returns:
        A dict with ``items``, ``total``, ``page``, ``page_size``,
        and ``total_pages``.
    """
    collection = db["suggestions"]

    # ── Build the filter query ──────────────────────────────────────────
    query: dict = {}

    if status is not None:
        query["status"] = status

    if source is not None:
        query["source"] = source

    # A candidate can appear as either the male or female side.
    if candidate_id is not None:
        oid = ObjectId(candidate_id)
        query["$or"] = [
            {"candidate_male_id": oid},
            {"candidate_female_id": oid},
        ]

    if created_by is not None:
        query["created_by"] = ObjectId(created_by)

    # ── Execute query ───────────────────────────────────────────────────
    total = await collection.count_documents(query)
    skip = (page - 1) * page_size

    cursor = (
        collection.find(query)
        .sort("created_at", -1)
        .skip(skip)
        .limit(page_size)
    )
    docs = await cursor.to_list(length=page_size)

    items = [SuggestionInDB(**doc) for doc in docs]
    total_pages = max(1, math.ceil(total / page_size))

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


# =============================================================================
# Update — Status Transition
# =============================================================================

async def update_suggestion_status(
    db: AsyncIOMotorDatabase,
    suggestion_id: str,
    *,
    new_status: str,
    changed_by: ObjectId,
    note: str | None = None,
) -> SuggestionInDB | None:
    """
    Update a suggestion's status and append a history entry.

    This is the primary way suggestions move through their lifecycle:
    ``proposed → reviewing → contacted → met → declined/engaged``.

    Two things happen atomically (in a single database operation):
        1. The ``status`` field is updated to the new value.
        2. A new entry is appended to the ``history`` array with the
           new status, timestamp, who made the change, and an optional note.

    Using ``$set`` + ``$push`` in a single ``update_one`` ensures the
    status field and history array are always consistent — there's no
    window where ``status`` says "met" but the history doesn't have
    the "met" entry.

    Args:
        db: The Motor database handle.
        suggestion_id: The suggestion's ``_id`` as a hex string.
        new_status: The status to transition to.
        changed_by: The ObjectId of the matchmaker making the change.
        note: Optional note explaining the change.

    Returns:
        The updated suggestion document, or None if the ID was not found.
    """
    now = datetime.utcnow()

    # Build the history entry that will be appended.
    history_entry = {
        "status": new_status,
        "at": now,
        "by": changed_by,
        "note": note,
    }

    result = await db["suggestions"].find_one_and_update(
        {"_id": ObjectId(suggestion_id)},
        {
            # $set updates the top-level status and timestamp.
            "$set": {
                "status": new_status,
                "updated_at": now,
            },
            # $push appends to the history array without replacing it.
            "$push": {
                "history": history_entry,
            },
        },
        return_document=True,
    )

    if result is None:
        return None
    return SuggestionInDB(**result)


# =============================================================================
# Update — AI Scores
# =============================================================================

async def update_suggestion_ai_scores(
    db: AsyncIOMotorDatabase,
    suggestion_id: str,
    *,
    ai_score: float,
    rerank_score: float,
    rerank_explanation_he: str,
    rerank_explanation_en: str,
    model_versions: dict,
) -> SuggestionInDB | None:
    """
    Overwrite the AI-generated scores on an existing suggestion.

    Called by the matching pipeline when a pair already exists as a suggestion
    but needs its scores refreshed (e.g. after a model upgrade or re-run).
    Status and history are intentionally NOT touched — human workflow state
    is preserved.

    Args:
        db: The Motor database handle.
        suggestion_id: The suggestion's ``_id`` as a hex string.
        ai_score: New cosine similarity score (0–1).
        rerank_score: New GPT rerank score (0–10).
        rerank_explanation_he: New Hebrew explanation.
        rerank_explanation_en: New English explanation.
        model_versions: Dict with ``embedding`` and ``rerank`` model names.

    Returns:
        The updated document, or None if not found.
    """
    result = await db["suggestions"].find_one_and_update(
        {"_id": ObjectId(suggestion_id)},
        {
            "$set": {
                "ai_score": ai_score,
                "rerank_score": rerank_score,
                "rerank_explanation_he": rerank_explanation_he,
                "rerank_explanation_en": rerank_explanation_en,
                "model_versions": model_versions,
                "updated_at": datetime.utcnow(),
            }
        },
        return_document=True,
    )
    if result is None:
        return None
    return SuggestionInDB(**result)


# =============================================================================
# Delete (Hard Delete — Admin Only)
# =============================================================================

async def delete_suggestion(
    db: AsyncIOMotorDatabase,
    suggestion_id: str,
) -> bool:
    """
    Permanently delete a suggestion document.

    Unlike candidates and matchmakers (which are soft-deleted), suggestions
    can be hard-deleted by admins. This is because:
        1. A wrongly-created suggestion has no downstream references — it's
           a leaf node in the data model.
        2. Matchmakers may want to "clean up" test suggestions or mistakes.
        3. The audit log separately records the deletion event, so we don't
           lose the history.

    Args:
        db: The Motor database handle.
        suggestion_id: The suggestion's ``_id`` as a hex string.

    Returns:
        True if a document was deleted, False if the ID was not found.
    """
    result = await db["suggestions"].delete_one(
        {"_id": ObjectId(suggestion_id)}
    )
    return result.deleted_count > 0
