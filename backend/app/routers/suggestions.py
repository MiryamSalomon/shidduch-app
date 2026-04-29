"""
Suggestions Router
===================
Endpoints for managing match suggestions between candidates.

Endpoints:
    - ``POST /suggestions`` — Manually create a suggestion.
    - ``GET /suggestions`` — List suggestions with filters and pagination.
    - ``GET /suggestions/{id}`` — Get a single suggestion's full detail.
    - ``PATCH /suggestions/{id}`` — Update a suggestion's status.
    - ``DELETE /suggestions/{id}`` — Hard-delete a suggestion (admin only).

Design decisions:
    - **Manual creation only here**: AI-generated suggestions come from the
      matching pipeline (``services/matcher.py``, not yet implemented), which
      calls ``suggestion_repo.upsert_suggestion`` directly. This router only
      handles human-created suggestions.
    - **Status transitions are not enforced**: Any status can be set at any
      time. Matchmakers know the process — no need for server-side FSM in v1.
    - **Hard delete for admins**: Unlike candidates (soft-deleted), a wrongly
      created suggestion can be permanently removed. It has no downstream
      references — it's a leaf node.
    - **Candidate validation on create**: Before creating a suggestion, both
      candidates must exist, have the correct gender, and not be archived.
"""

from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db import get_db
from app.deps import get_current_matchmaker, require_admin
from app.models.common import PaginatedResponse, SuggestionSource, SuggestionStatus
from app.models.matchmaker import MatchmakerInDB
from app.models.suggestion import (
    SuggestionCreate,
    SuggestionInDB,
    SuggestionOut,
    SuggestionUpdateStatus,
)
from app.repositories import candidate_repo, suggestion_repo

router = APIRouter(prefix="/suggestions", tags=["Suggestions"])


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _to_out(s: SuggestionInDB) -> SuggestionOut:
    return SuggestionOut(
        id=str(s.id),
        candidate_male_id=str(s.candidate_male_id),
        candidate_female_id=str(s.candidate_female_id),
        pair_key=s.pair_key,
        source=s.source,
        status=s.status,
        ai_score=s.ai_score,
        rerank_score=s.rerank_score,
        rerank_explanation_he=s.rerank_explanation_he,
        rerank_explanation_en=s.rerank_explanation_en,
        model_versions=s.model_versions,
        history=s.history,
        created_by=str(s.created_by) if s.created_by else None,
        created_at=s.created_at,
        updated_at=s.updated_at,
    )


def _require_found(suggestion: SuggestionInDB | None) -> SuggestionInDB:
    if suggestion is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Suggestion not found.",
        )
    return suggestion


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=SuggestionOut,
    status_code=status.HTTP_201_CREATED,
    summary="Manually create a match suggestion",
    responses={
        201: {"description": "Suggestion created"},
        400: {"description": "Invalid candidate ID"},
        404: {"description": "Candidate not found"},
        409: {"description": "Suggestion for this pair already exists"},
        422: {"description": "Validation error"},
    },
)
async def create_suggestion(
    body: SuggestionCreate,
    current_user: MatchmakerInDB = Depends(get_current_matchmaker),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> SuggestionOut:
    """
    Manually create a suggestion for a male/female candidate pair.

    Validates that:
        - Both candidate IDs are valid and exist.
        - The male candidate has ``gender="male"``.
        - The female candidate has ``gender="female"``.
        - Neither candidate is archived.
        - The pair has not already been suggested (unique ``pair_key``).

    Args:
        body: The male and female candidate IDs, plus an optional note.
        current_user: The authenticated matchmaker (set as ``created_by``).
        db: The database handle.

    Returns:
        The newly created suggestion.

    Raises:
        HTTPException(404): If either candidate does not exist.
        HTTPException(422): If either candidate has the wrong gender or is archived.
        HTTPException(409): If a suggestion for this pair already exists.
    """
    # ── Validate male candidate ─────────────────────────────────────────
    try:
        male = await candidate_repo.get_candidate_by_id(db, body.candidate_male_id)
    except InvalidId:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Male candidate '{body.candidate_male_id}' not found.",
        )
    if male is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Male candidate '{body.candidate_male_id}' not found.",
        )
    if male.gender.value != "male":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Candidate '{body.candidate_male_id}' is not male.",
        )
    if male.status.value == "archived":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Male candidate '{body.candidate_male_id}' is archived.",
        )

    # ── Validate female candidate ───────────────────────────────────────
    try:
        female = await candidate_repo.get_candidate_by_id(db, body.candidate_female_id)
    except InvalidId:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Female candidate '{body.candidate_female_id}' not found.",
        )
    if female is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Female candidate '{body.candidate_female_id}' not found.",
        )
    if female.gender.value != "female":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Candidate '{body.candidate_female_id}' is not female.",
        )
    if female.status.value == "archived":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Female candidate '{body.candidate_female_id}' is archived.",
        )

    # ── Build and insert the suggestion ────────────────────────────────
    pair_key = f"{body.candidate_male_id}:{body.candidate_female_id}"

    data = {
        "candidate_male_id": male.id,
        "candidate_female_id": female.id,
        "pair_key": pair_key,
        "source": "manual",
        "created_by": current_user.id,
        "note": body.note,
    }

    suggestion = await suggestion_repo.create_suggestion(db, data)

    if suggestion is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A suggestion for this pair already exists.",
        )

    return _to_out(suggestion)


@router.get(
    "",
    response_model=PaginatedResponse,
    summary="List suggestions with optional filters",
)
async def list_suggestions(
    status_filter: SuggestionStatus | None = Query(
        default=None, alias="status", description="Filter by suggestion status",
    ),
    source: SuggestionSource | None = Query(
        default=None, description="Filter by source (ai or manual)",
    ),
    candidate_id: str | None = Query(
        default=None, description="Show suggestions involving this candidate (either side)",
    ),
    created_by: str | None = Query(
        default=None, description="Filter by creating matchmaker ID",
    ),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    current_user: MatchmakerInDB = Depends(get_current_matchmaker),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> PaginatedResponse:
    """
    List suggestions with optional filters and pagination.

    When ``candidate_id`` is provided, returns all suggestions where that
    candidate appears on either the male or female side. Useful for the
    candidate detail page's "suggestions" tab.

    Args:
        status_filter: Restrict to a specific lifecycle stage.
        source: Restrict to AI-generated or manual suggestions.
        candidate_id: Restrict to suggestions involving this candidate.
        created_by: Restrict to suggestions created by this matchmaker.
        page: Page number (1-based).
        page_size: Items per page (1–100).
        current_user: The authenticated matchmaker.
        db: The database handle.

    Returns:
        A paginated list of ``SuggestionOut`` items sorted newest-first.

    Raises:
        HTTPException(400): If ``candidate_id`` or ``created_by`` is not a
            valid ObjectId format.
    """
    # Validate optional ID params before hitting the repo.
    if candidate_id is not None:
        from bson import ObjectId as BsonObjectId
        if not BsonObjectId.is_valid(candidate_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid candidate_id: '{candidate_id}'.",
            )
    if created_by is not None:
        from bson import ObjectId as BsonObjectId
        if not BsonObjectId.is_valid(created_by):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid created_by: '{created_by}'.",
            )

    result = await suggestion_repo.list_suggestions(
        db,
        status=status_filter.value if status_filter else None,
        source=source.value if source else None,
        candidate_id=candidate_id,
        created_by=created_by,
        page=page,
        page_size=page_size,
    )
    result["items"] = [_to_out(s) for s in result["items"]]
    return PaginatedResponse(**result)


@router.get(
    "/{suggestion_id}",
    response_model=SuggestionOut,
    summary="Get a suggestion's full detail",
    responses={
        404: {"description": "Suggestion not found"},
    },
)
async def get_suggestion(
    suggestion_id: str,
    current_user: MatchmakerInDB = Depends(get_current_matchmaker),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> SuggestionOut:
    """
    Retrieve a single suggestion by ID, including the full status history.

    Args:
        suggestion_id: The suggestion's MongoDB ObjectId as a 24-char hex string.
        current_user: The authenticated matchmaker.
        db: The database handle.

    Returns:
        The suggestion's full detail.

    Raises:
        HTTPException(404): If the ID is invalid or the suggestion doesn't exist.
    """
    try:
        suggestion = await suggestion_repo.get_suggestion_by_id(db, suggestion_id)
    except InvalidId:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Suggestion not found.",
        )
    return _to_out(_require_found(suggestion))


@router.patch(
    "/{suggestion_id}",
    response_model=SuggestionOut,
    summary="Update a suggestion's status",
    responses={
        404: {"description": "Suggestion not found"},
    },
)
async def update_suggestion_status(
    suggestion_id: str,
    body: SuggestionUpdateStatus,
    current_user: MatchmakerInDB = Depends(get_current_matchmaker),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> SuggestionOut:
    """
    Move a suggestion to a new status and record it in the history.

    The status change is atomic: the ``status`` field and the ``history``
    array are updated in a single database operation. The history entry
    records the new status, the timestamp, the acting matchmaker, and an
    optional note.

    Status transitions are not enforced server-side — matchmakers can set
    any status at any time (they know the process).

    Args:
        suggestion_id: The suggestion's MongoDB ObjectId.
        body: The new status and an optional explanatory note.
        current_user: The authenticated matchmaker (recorded in history).
        db: The database handle.

    Returns:
        The updated suggestion with the new status and appended history entry.

    Raises:
        HTTPException(404): If the suggestion is not found.
    """
    try:
        suggestion = await suggestion_repo.update_suggestion_status(
            db,
            suggestion_id,
            new_status=body.status.value,
            changed_by=current_user.id,
            note=body.note,
        )
    except InvalidId:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Suggestion not found.",
        )
    return _to_out(_require_found(suggestion))


@router.delete(
    "/{suggestion_id}",
    status_code=status.HTTP_200_OK,
    summary="Permanently delete a suggestion (admin only)",
    responses={
        404: {"description": "Suggestion not found"},
    },
)
async def delete_suggestion(
    suggestion_id: str,
    admin: MatchmakerInDB = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    """
    Permanently delete a suggestion (admin only).

    Unlike candidates, suggestions can be hard-deleted because they are leaf
    nodes — no other documents reference them. This allows admins to clean up
    test data or mistakes.

    Args:
        suggestion_id: The suggestion's MongoDB ObjectId.
        admin: The authenticated admin matchmaker.
        db: The database handle.

    Returns:
        A confirmation message.

    Raises:
        HTTPException(404): If the suggestion is not found.
    """
    try:
        deleted = await suggestion_repo.delete_suggestion(db, suggestion_id)
    except InvalidId:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Suggestion not found.",
        )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Suggestion not found.",
        )
    return {"detail": f"Suggestion '{suggestion_id}' has been permanently deleted."}
