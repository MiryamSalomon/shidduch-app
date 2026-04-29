"""
Candidate Repository
=====================
Data access layer for the ``candidates`` collection in MongoDB.

This is the most feature-rich repository because candidates are the core
entity of the system. It handles:

    - **CRUD**: Create, read, update, and soft-delete candidates.
    - **Filtered listing**: Gender, status, community, age range, and
      free-text search — all combined into a single query with pagination.
    - **Denormalisation**: Automatically recomputes ``age`` (from date of
      birth) and ``num_brothers`` / ``num_sisters`` (from the siblings
      array) on every write, so these fields are always up-to-date for
      index-backed queries.
    - **Embedding updates**: A dedicated function to persist new embedding
      vectors and their metadata after the OpenAI service computes them.

Design decisions:
    - **Soft delete**: ``delete_candidate`` sets ``status="archived"``
      instead of removing the document. This preserves the audit trail
      and allows recovery.
    - **No embedding logic here**: The repository stores embeddings but
      doesn't compute them. That's the embedding service's job
      (``services/embeddings.py``). Separation of concerns.
    - **``$regex`` for text search**: MongoDB Atlas has full-text search,
      but it requires a separate Atlas Search index. For v1 with a small
      dataset (~hundreds of candidates), case-insensitive regex on
      ``first_name`` / ``last_name`` is sufficient and needs no extra
      infrastructure.
"""

import math
from datetime import date, datetime

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.candidate import CandidateInDB


# =============================================================================
# Helper Functions
# =============================================================================

def _compute_age(date_of_birth: date) -> int:
    """
    Compute current age in years from a date of birth.

    Uses today's date and accounts for whether the birthday has occurred
    this year. For example, if someone was born on 2002-06-15 and today
    is 2026-04-21, they are 23 (not yet 24).

    Args:
        date_of_birth: The candidate's birth date.

    Returns:
        Age in whole years.
    """
    today = date.today()
    age = today.year - date_of_birth.year

    # If their birthday hasn't happened yet this year, subtract one.
    if (today.month, today.day) < (date_of_birth.month, date_of_birth.day):
        age -= 1

    return age


def _count_siblings(siblings: list[dict]) -> tuple[int, int]:
    """
    Count the number of brothers and sisters in a siblings list.

    Args:
        siblings: A list of sibling dicts, each with a ``relation`` field
            that is either "brother" or "sister".

    Returns:
        A tuple of (num_brothers, num_sisters).
    """
    brothers = sum(1 for s in siblings if s.get("relation") == "brother")
    sisters = sum(1 for s in siblings if s.get("relation") == "sister")
    return brothers, sisters


def _apply_denormalisations(data: dict) -> dict:
    """
    Recompute all denormalised fields on a candidate data dict.

    Called before every insert or update to ensure ``age``,
    ``num_brothers``, and ``num_sisters`` are consistent with
    the source fields (``date_of_birth`` and ``family.siblings``).

    Args:
        data: The candidate data dict (may be a full document or
            a partial update).

    Returns:
        The same dict, modified in place, with denormalised fields updated.
    """
    # Recompute age from date of birth.
    if "date_of_birth" in data:
        dob = data["date_of_birth"]
        if isinstance(dob, str):
            dob = date.fromisoformat(dob)
        data["age"] = _compute_age(dob)

    # Recompute sibling counts from the siblings array.
    if "family" in data and isinstance(data["family"], dict):
        siblings = data["family"].get("siblings", [])
        brothers, sisters = _count_siblings(siblings)
        data["family"]["num_brothers"] = brothers
        data["family"]["num_sisters"] = sisters

    return data


# =============================================================================
# Create
# =============================================================================

async def create_candidate(
    db: AsyncIOMotorDatabase,
    data: dict,
) -> CandidateInDB:
    """
    Insert a new candidate document into the database.

    Before inserting, this function:
        1. Recomputes ``age`` from ``date_of_birth``.
        2. Recomputes ``num_brothers`` / ``num_sisters`` from siblings.
        3. Sets ``created_at`` and ``updated_at`` timestamps.
        4. Initialises embedding fields to their defaults (empty).

    The caller (router or service) should convert the ``CandidateCreate``
    Pydantic model to a dict via ``.model_dump()`` before passing it here.

    After insertion, the embedding service should be called to generate
    the profile and preferences embeddings asynchronously.

    Args:
        db: The Motor database handle.
        data: A dict of candidate fields from ``CandidateCreate``.

    Returns:
        The newly created candidate as a ``CandidateInDB`` instance.
    """
    now = datetime.utcnow()
    data["created_at"] = now
    data["updated_at"] = now

    # Initialise embedding fields (will be populated by the embedding service).
    data.setdefault("profile_embedding", [])
    data.setdefault("preferences_embedding", [])
    data.setdefault("profile_text_hash", "")
    data.setdefault("preferences_text_hash", "")
    data.setdefault("embedding_model", "")
    data.setdefault("embedding_updated_at", None)

    # Recompute denormalised fields (age, sibling counts).
    _apply_denormalisations(data)

    result = await db["candidates"].insert_one(data)
    data["_id"] = result.inserted_id

    return CandidateInDB(**data)


# =============================================================================
# Read — Single Document
# =============================================================================

async def get_candidate_by_id(
    db: AsyncIOMotorDatabase,
    candidate_id: str,
) -> CandidateInDB | None:
    """
    Find a candidate by their MongoDB ObjectId.

    Returns the full document including embedding fields. The router
    is responsible for converting to ``CandidateOut`` (which strips
    embeddings) before returning to the client.

    Args:
        db: The Motor database handle.
        candidate_id: The candidate's ``_id`` as a 24-character hex string.

    Returns:
        The candidate document, or None if not found.
    """
    doc = await db["candidates"].find_one({"_id": ObjectId(candidate_id)})
    if doc is None:
        return None
    return CandidateInDB(**doc)


# =============================================================================
# Read — List (Paginated + Filtered)
# =============================================================================

async def list_candidates(
    db: AsyncIOMotorDatabase,
    *,
    gender: str | None = None,
    status: str | None = None,
    community: str | None = None,
    age_min: int | None = None,
    age_max: int | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """
    List candidates with optional filters and pagination.

    Filters are combined with AND logic: a candidate must match ALL
    provided filters to be included. Omitted filters are ignored
    (no restriction on that field).

    The ``search`` parameter does a case-insensitive partial match on
    ``first_name`` or ``last_name``. For example, searching "כהן" will
    find "כהן", "כהנא", etc. This uses MongoDB's ``$regex`` operator,
    which is adequate for the expected dataset size (~hundreds of candidates).
    For thousands, an Atlas Search index would be more efficient.

    Results are sorted by creation date (newest first).

    Args:
        db: The Motor database handle.
        gender: Filter by gender ("male" or "female"). None = any.
        status: Filter by status ("active", "paused", etc.). None = any.
        community: Filter by community ("litvish", etc.). None = any.
        age_min: Minimum age (inclusive). None = no lower bound.
        age_max: Maximum age (inclusive). None = no upper bound.
        search: Free-text search on first/last name. None = no search.
        page: The page number (1-based).
        page_size: Number of items per page.

    Returns:
        A dict with ``items`` (list of ``CandidateInDB``), ``total``,
        ``page``, ``page_size``, and ``total_pages``.
    """
    collection = db["candidates"]

    # ── Build the filter query ──────────────────────────────────────────
    query: dict = {}

    if gender is not None:
        query["gender"] = gender

    if status is not None:
        query["status"] = status

    if community is not None:
        query["community"] = community

    # Age range filter — uses the denormalised ``age`` field so it hits
    # the compound index ``idx_gender_status_age``.
    if age_min is not None or age_max is not None:
        age_filter: dict = {}
        if age_min is not None:
            age_filter["$gte"] = age_min
        if age_max is not None:
            age_filter["$lte"] = age_max
        query["age"] = age_filter

    # Text search on name — case-insensitive regex.
    if search:
        query["$or"] = [
            {"first_name": {"$regex": search, "$options": "i"}},
            {"last_name": {"$regex": search, "$options": "i"}},
        ]

    # ── Projection: exclude embedding vectors from list queries ─────────
    # Embeddings are 3072 floats each (~25KB per vector). When listing
    # many candidates, sending these would waste bandwidth. They're only
    # needed by the matching pipeline, which reads them via get_by_id.
    projection = {
        "profile_embedding": 0,
        "preferences_embedding": 0,
    }

    # ── Execute query ───────────────────────────────────────────────────
    total = await collection.count_documents(query)
    skip = (page - 1) * page_size

    cursor = (
        collection.find(query, projection)
        .sort("created_at", -1)
        .skip(skip)
        .limit(page_size)
    )
    docs = await cursor.to_list(length=page_size)

    items = [CandidateInDB(**doc) for doc in docs]
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

async def update_candidate(
    db: AsyncIOMotorDatabase,
    candidate_id: str,
    update_data: dict,
) -> CandidateInDB | None:
    """
    Partially update a candidate document.

    Before applying the update:
        1. Recomputes ``age`` if ``date_of_birth`` changed.
        2. Recomputes ``num_brothers`` / ``num_sisters`` if ``family`` changed.
        3. Sets ``updated_at`` to now.

    Only the fields present in ``update_data`` are modified.

    Note: If ``character_traits`` or ``preferences`` changed, the router
    should call the embedding service AFTER this update to recompute
    embeddings. The repository doesn't trigger embedding — it only
    stores data.

    Args:
        db: The Motor database handle.
        candidate_id: The candidate's ``_id`` as a hex string.
        update_data: A dict of fields to update.

    Returns:
        The updated candidate document, or None if the ID was not found.
    """
    update_data["updated_at"] = datetime.utcnow()

    # Recompute denormalised fields based on what's changing.
    _apply_denormalisations(update_data)

    result = await db["candidates"].find_one_and_update(
        {"_id": ObjectId(candidate_id)},
        {"$set": update_data},
        return_document=True,
    )

    if result is None:
        return None
    return CandidateInDB(**result)


# =============================================================================
# Update — Embeddings
# =============================================================================

async def update_candidate_embeddings(
    db: AsyncIOMotorDatabase,
    candidate_id: str,
    *,
    profile_embedding: list[float] | None = None,
    preferences_embedding: list[float] | None = None,
    profile_text_hash: str | None = None,
    preferences_text_hash: str | None = None,
    embedding_model: str | None = None,
) -> bool:
    """
    Persist new embedding vectors and their metadata for a candidate.

    Called by the embedding service (``services/embeddings.py``) after
    computing vectors via OpenAI. Only the provided fields are updated —
    for example, if only the profile text changed, only ``profile_embedding``
    and ``profile_text_hash`` are written.

    This is a separate function from ``update_candidate`` because embedding
    updates have a different access pattern:
        - They're called from the service layer, not from HTTP PATCHes.
        - They update specific technical fields, not user-facing data.
        - They need the ``embedding_updated_at`` timestamp.

    Args:
        db: The Motor database handle.
        candidate_id: The candidate's ``_id`` as a hex string.
        profile_embedding: New profile vector (3072 floats), or None to skip.
        preferences_embedding: New preferences vector, or None to skip.
        profile_text_hash: SHA-256 hash of the profile text that was embedded.
        preferences_text_hash: SHA-256 hash of the preferences text.
        embedding_model: The OpenAI model name used for embedding.

    Returns:
        True if the document was found and updated, False if not found.
    """
    update_fields: dict = {
        "updated_at": datetime.utcnow(),
        "embedding_updated_at": datetime.utcnow(),
    }

    if profile_embedding is not None:
        update_fields["profile_embedding"] = profile_embedding
    if preferences_embedding is not None:
        update_fields["preferences_embedding"] = preferences_embedding
    if profile_text_hash is not None:
        update_fields["profile_text_hash"] = profile_text_hash
    if preferences_text_hash is not None:
        update_fields["preferences_text_hash"] = preferences_text_hash
    if embedding_model is not None:
        update_fields["embedding_model"] = embedding_model

    result = await db["candidates"].update_one(
        {"_id": ObjectId(candidate_id)},
        {"$set": update_fields},
    )

    return result.matched_count > 0


# =============================================================================
# Delete (Soft Delete)
# =============================================================================

async def delete_candidate(
    db: AsyncIOMotorDatabase,
    candidate_id: str,
) -> CandidateInDB | None:
    """
    Soft-delete a candidate by setting their status to ``archived``.

    We never hard-delete candidates because:
        1. Suggestions reference candidate IDs — deleting would orphan them.
        2. The audit log references candidate IDs.
        3. Archived candidates can be restored by changing status back to
           ``active``.
        4. Archived candidates are excluded from matching (the pipeline
           filters by ``status="active"``).

    Args:
        db: The Motor database handle.
        candidate_id: The candidate's ``_id`` as a hex string.

    Returns:
        The updated candidate document, or None if the ID was not found.
    """
    return await update_candidate(
        db,
        candidate_id,
        {"status": "archived"},
    )
