"""
Candidates Router
==================
CRUD endpoints for managing shidduch candidates.

Endpoints:
    - ``POST /candidates`` — Create a new candidate.
    - ``GET /candidates`` — List candidates with filters and pagination.
    - ``GET /candidates/{id}`` — Get a single candidate's full profile.
    - ``PATCH /candidates/{id}`` — Partially update a candidate.
    - ``DELETE /candidates/{id}`` — Soft-delete (archive) a candidate.

All endpoints require authentication. Any active matchmaker can create and
manage candidates — admin role is not required.

Design decisions:
    - **Embeddings via background tasks**: After create or update, embedding
      generation is queued as a FastAPI ``BackgroundTask``. The response
      returns immediately — ``has_embeddings`` will be False on the first
      create, then True once the background task completes.
    - ``POST /candidates/{id}/embed`` triggers a manual re-embed (e.g. after
      a model upgrade or if the background task failed).
    - **Soft delete**: DELETE sets status to "archived". Candidates are never
      hard-deleted because suggestions reference their IDs.
    - **Audit trail**: ``created_by`` and ``updated_by`` are set to the current
      matchmaker's ObjectId on every write.
"""

from bson.errors import InvalidId
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db import get_db
from app.deps import get_current_matchmaker
from app.models.candidate import (
    CandidateCreate,
    CandidateInDB,
    CandidateOut,
    CandidateSummary,
    CandidateUpdate,
)
from app.models.common import CandidateStatus, Community, Gender, PaginatedResponse
from app.models.matchmaker import MatchmakerInDB
from app.repositories import candidate_repo
from app.services import embeddings

router = APIRouter(prefix="/candidates", tags=["Candidates"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_out(c: CandidateInDB) -> CandidateOut:
    return CandidateOut(
        id=str(c.id),
        first_name=c.first_name,
        last_name=c.last_name,
        gender=c.gender,
        date_of_birth=c.date_of_birth,
        age=c.age,
        city=c.city,
        community=c.community,
        education=c.education,
        family=c.family,
        character_traits=c.character_traits,
        preferences=c.preferences,
        status=c.status,
        notes=c.notes,
        has_embeddings=len(c.profile_embedding) > 0,
        embedding_model=c.embedding_model,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


def _to_summary(c: CandidateInDB) -> CandidateSummary:
    return CandidateSummary(
        id=str(c.id),
        first_name=c.first_name,
        last_name=c.last_name,
        gender=c.gender,
        age=c.age,
        city=c.city,
        community=c.community,
        current_institution=c.education.current_institution,
        status=c.status,
        has_embeddings=len(c.profile_embedding) > 0,
    )


def _require_found(candidate: CandidateInDB | None) -> CandidateInDB:
    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found.",
        )
    return candidate


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=CandidateOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new candidate",
    responses={
        201: {"description": "Candidate created"},
        422: {"description": "Validation error"},
    },
)
async def create_candidate(
    body: CandidateCreate,
    background_tasks: BackgroundTasks,
    current_user: MatchmakerInDB = Depends(get_current_matchmaker),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> CandidateOut:
    """
    Create a new candidate profile.

    Automatically computes:
        - ``age`` from ``date_of_birth``.
        - ``num_brothers`` / ``num_sisters`` from the siblings list.

    Embedding generation is queued as a background task — the response
    returns immediately. ``has_embeddings`` will be False until the task
    completes (typically within a few seconds).

    Args:
        body: The candidate's full profile.
        background_tasks: FastAPI background task queue.
        current_user: The authenticated matchmaker (set as ``created_by``).
        db: The database handle.

    Returns:
        The newly created candidate (``has_embeddings`` will be False initially).
    """
    data = body.model_dump(mode="json")
    data["created_by"] = current_user.id
    data["updated_by"] = current_user.id

    candidate = await candidate_repo.create_candidate(db, data)
    background_tasks.add_task(embeddings.embed_candidate, db, candidate)
    return _to_out(candidate)


@router.get(
    "",
    response_model=PaginatedResponse,
    summary="List candidates with optional filters",
)
async def list_candidates(
    gender: Gender | None = Query(default=None, description="Filter by gender"),
    status_filter: CandidateStatus | None = Query(
        default=None, alias="status", description="Filter by status",
    ),
    community: Community | None = Query(default=None, description="Filter by community"),
    age_min: int | None = Query(default=None, ge=0, le=120, description="Minimum age"),
    age_max: int | None = Query(default=None, ge=0, le=120, description="Maximum age"),
    search: str | None = Query(
        default=None, max_length=100, description="Search by first or last name",
    ),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    current_user: MatchmakerInDB = Depends(get_current_matchmaker),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> PaginatedResponse:
    """
    List candidates with optional filters and pagination.

    All filters are optional and combined with AND logic. Results are sorted
    by creation date (newest first). Returns lightweight ``CandidateSummary``
    objects — use ``GET /candidates/{id}`` for the full profile.

    Args:
        gender: Filter to only male or female candidates.
        status_filter: Filter by lifecycle status (defaults to all statuses).
        community: Filter by religious community.
        age_min: Inclusive minimum age.
        age_max: Inclusive maximum age.
        search: Case-insensitive partial match on first or last name.
        page: Page number (1-based).
        page_size: Items per page (1–100).
        current_user: The authenticated matchmaker.
        db: The database handle.

    Returns:
        A paginated list of ``CandidateSummary`` items.
    """
    result = await candidate_repo.list_candidates(
        db,
        gender=gender.value if gender else None,
        status=status_filter.value if status_filter else None,
        community=community.value if community else None,
        age_min=age_min,
        age_max=age_max,
        search=search,
        page=page,
        page_size=page_size,
    )
    result["items"] = [_to_summary(c) for c in result["items"]]
    return PaginatedResponse(**result)


@router.get(
    "/{candidate_id}",
    response_model=CandidateOut,
    summary="Get a candidate's full profile",
    responses={
        404: {"description": "Candidate not found"},
    },
)
async def get_candidate(
    candidate_id: str,
    current_user: MatchmakerInDB = Depends(get_current_matchmaker),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> CandidateOut:
    """
    Retrieve a candidate's full profile by ID.

    Returns all fields except the raw embedding vectors (those are ~25KB each
    and are only needed internally by the matching pipeline).

    Args:
        candidate_id: The candidate's MongoDB ObjectId as a 24-char hex string.
        current_user: The authenticated matchmaker.
        db: The database handle.

    Returns:
        The candidate's full profile.

    Raises:
        HTTPException(404): If the ID is invalid or the candidate doesn't exist.
    """
    try:
        candidate = await candidate_repo.get_candidate_by_id(db, candidate_id)
    except InvalidId:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found.",
        )
    return _to_out(_require_found(candidate))


@router.patch(
    "/{candidate_id}",
    response_model=CandidateOut,
    summary="Partially update a candidate",
    responses={
        400: {"description": "No fields provided"},
        404: {"description": "Candidate not found"},
    },
)
async def update_candidate(
    candidate_id: str,
    body: CandidateUpdate,
    background_tasks: BackgroundTasks,
    current_user: MatchmakerInDB = Depends(get_current_matchmaker),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> CandidateOut:
    """
    Partially update a candidate's profile.

    Only the fields present in the request body are modified. Omitted fields
    are unchanged. Denormalised fields (``age``, sibling counts) are
    recomputed automatically when their source fields change.

    If ``character_traits``, ``preferences``, or any profile field changes,
    re-embedding is queued as a background task. The embedding service uses
    hash comparison to skip unnecessary API calls.

    Args:
        candidate_id: The candidate's MongoDB ObjectId.
        body: Fields to update (all optional; at least one required).
        background_tasks: FastAPI background task queue.
        current_user: The authenticated matchmaker (set as ``updated_by``).
        db: The database handle.

    Returns:
        The updated candidate's full profile.

    Raises:
        HTTPException(400): If no fields are provided.
        HTTPException(404): If the candidate is not found.
    """
    update_data = body.model_dump(exclude_unset=True, mode="json")

    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update.",
        )

    update_data["updated_by"] = current_user.id

    # Determine whether any embedding-relevant field is changing.
    _EMBEDDING_FIELDS = {
        "character_traits", "preferences", "community", "city",
        "education", "family", "date_of_birth",
    }
    needs_reembed = bool(_EMBEDDING_FIELDS & update_data.keys())

    try:
        candidate = await candidate_repo.update_candidate(db, candidate_id, update_data)
    except InvalidId:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found.",
        )

    candidate = _require_found(candidate)

    if needs_reembed:
        background_tasks.add_task(embeddings.embed_candidate, db, candidate)

    return _to_out(candidate)


@router.delete(
    "/{candidate_id}",
    status_code=status.HTTP_200_OK,
    summary="Archive (soft-delete) a candidate",
    responses={
        404: {"description": "Candidate not found"},
    },
)
async def delete_candidate(
    candidate_id: str,
    current_user: MatchmakerInDB = Depends(get_current_matchmaker),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    """
    Soft-delete a candidate by setting their status to ``archived``.

    The document is never removed from the database because suggestions
    reference candidate IDs — hard deletion would orphan them. Archived
    candidates are excluded from the matching pipeline automatically.

    To restore an archived candidate, use PATCH with ``status: "active"``.

    Args:
        candidate_id: The candidate's MongoDB ObjectId.
        current_user: The authenticated matchmaker.
        db: The database handle.

    Returns:
        A confirmation message.

    Raises:
        HTTPException(404): If the candidate is not found.
    """
    try:
        candidate = await candidate_repo.delete_candidate(db, candidate_id)
    except InvalidId:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found.",
        )

    _require_found(candidate)
    return {
        "detail": (
            f"Candidate '{candidate.first_name} {candidate.last_name}' "
            "has been archived."
        ),
    }


@router.post(
    "/{candidate_id}/embed",
    response_model=CandidateOut,
    summary="Manually trigger embedding (re)generation",
    responses={
        404: {"description": "Candidate not found"},
    },
)
async def trigger_embed(
    candidate_id: str,
    background_tasks: BackgroundTasks,
    force: bool = Query(
        default=False,
        description="Force re-embed even if hashes are current (use after model upgrade)",
    ),
    current_user: MatchmakerInDB = Depends(get_current_matchmaker),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> CandidateOut:
    """
    Manually queue an embedding run for a candidate.

    Normally embeddings are generated automatically in the background after
    create and update. Use this endpoint to:
        - Retry a failed embedding (e.g. after an OpenAI outage).
        - Force re-embedding after upgrading the embedding model (``force=True``).

    The embedding runs in the background — this endpoint returns immediately
    with the current candidate state. Check ``has_embeddings`` on a subsequent
    GET to confirm completion.

    Args:
        candidate_id: The candidate's MongoDB ObjectId.
        background_tasks: FastAPI background task queue.
        force: If True, re-embed even if hashes indicate no change.
        current_user: The authenticated matchmaker.
        db: The database handle.

    Returns:
        The current candidate profile (``has_embeddings`` may still be False
        if the background task hasn't completed yet).

    Raises:
        HTTPException(404): If the candidate is not found.
    """
    try:
        candidate = await candidate_repo.get_candidate_by_id(db, candidate_id)
    except InvalidId:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found.",
        )

    candidate = _require_found(candidate)
    background_tasks.add_task(embeddings.embed_candidate, db, candidate, force=force)
    return _to_out(candidate)
