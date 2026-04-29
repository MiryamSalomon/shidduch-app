"""
Matchmakers Router
===================
Admin-only endpoints for managing matchmaker (shadchan) user accounts.

All endpoints in this router require admin privileges — they use the
``require_admin`` dependency, which first authenticates the user (valid JWT,
active account) and then checks that their role is ``admin``.

Endpoints:
    - ``POST /matchmakers`` — Create a new matchmaker account.
    - ``GET /matchmakers`` — List all matchmaker accounts (paginated).
    - ``GET /matchmakers/{id}`` — Get a single matchmaker's details.
    - ``PATCH /matchmakers/{id}`` — Update a matchmaker's profile or role.
    - ``DELETE /matchmakers/{id}`` — Deactivate (soft-delete) a matchmaker.

Design decisions:
    - **No public registration**: Accounts are created only by admins or
      the bootstrap script. This is a closed system for a specific team.
    - **Password hashing in the router**: The router hashes the plain-text
      password before passing it to the repository. The repository never
      sees plain-text passwords — it only stores and retrieves hashes.
    - **Soft delete**: ``DELETE`` sets ``is_active=False`` rather than
      removing the document. This preserves audit trail integrity.
    - **Self-protection**: An admin cannot deactivate their own account
      (to prevent locking everyone out).
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db import get_db
from app.deps import require_admin
from app.models.common import PaginatedResponse
from app.models.matchmaker import (
    MatchmakerCreate,
    MatchmakerInDB,
    MatchmakerOut,
    MatchmakerUpdate,
)
from app.repositories import matchmaker_repo
from app.security import hash_password

router = APIRouter(prefix="/matchmakers", tags=["Matchmakers"])


# ---------------------------------------------------------------------------
# Helper — Convert MatchmakerInDB to MatchmakerOut
# ---------------------------------------------------------------------------

def _to_out(m: MatchmakerInDB) -> MatchmakerOut:
    """
    Convert an internal matchmaker document to the public API response.

    Strips sensitive fields (password_hash, failed_attempts, locked_until)
    and converts the ObjectId to a string.

    Args:
        m: The internal matchmaker document.

    Returns:
        A safe-to-return ``MatchmakerOut`` instance.
    """
    return MatchmakerOut(
        id=str(m.id),
        username=m.username,
        display_name=m.display_name,
        email=m.email,
        role=m.role,
        is_active=m.is_active,
        last_login_at=m.last_login_at,
        created_at=m.created_at,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=MatchmakerOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new matchmaker account",
)
async def create_matchmaker(
    body: MatchmakerCreate,
    admin: MatchmakerInDB = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> MatchmakerOut:
    """
    Create a new matchmaker account (admin only).

    Steps:
        1. Check that the username is not already taken.
        2. Check that the email (if provided) is not already taken.
        3. Hash the plain-text password with argon2id.
        4. Insert the document into the ``matchmakers`` collection.

    Args:
        body: The new matchmaker's details (username, password, etc.).
        admin: The authenticated admin (injected by ``require_admin``).
        db: The database handle.

    Returns:
        The newly created matchmaker's public profile.

    Raises:
        HTTPException(409): If the username or email is already in use.
    """
    # ── Uniqueness checks ───────────────────────────────────────────────
    existing = await matchmaker_repo.get_matchmaker_by_username(db, body.username)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{body.username}' is already taken.",
        )

    if body.email:
        existing_email = await matchmaker_repo.get_matchmaker_by_email(db, body.email)
        if existing_email is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Email '{body.email}' is already in use.",
            )

    # ── Hash the password and create the document ───────────────────────
    data = body.model_dump()
    plain_password = data.pop("password")  # Remove plain text
    data["password_hash"] = hash_password(plain_password)  # Store hash

    matchmaker = await matchmaker_repo.create_matchmaker(db, data)
    return _to_out(matchmaker)


@router.get(
    "",
    response_model=PaginatedResponse,
    summary="List all matchmaker accounts",
)
async def list_matchmakers(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    admin: MatchmakerInDB = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> PaginatedResponse:
    """
    List all matchmaker accounts with pagination (admin only).

    Returns a paginated list sorted by creation date (newest first).
    Includes all accounts (active and inactive).

    Args:
        page: The page number (1-based).
        page_size: Number of items per page (1–100).
        admin: The authenticated admin.
        db: The database handle.

    Returns:
        A paginated list of matchmaker profiles.
    """
    result = await matchmaker_repo.list_matchmakers(
        db, page=page, page_size=page_size,
    )

    # Convert internal models to public output.
    result["items"] = [_to_out(m) for m in result["items"]]
    return PaginatedResponse(**result)


@router.get(
    "/{matchmaker_id}",
    response_model=MatchmakerOut,
    summary="Get a matchmaker's details",
)
async def get_matchmaker(
    matchmaker_id: str,
    admin: MatchmakerInDB = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> MatchmakerOut:
    """
    Get a single matchmaker's public profile by ID (admin only).

    Args:
        matchmaker_id: The matchmaker's MongoDB ObjectId as a hex string.
        admin: The authenticated admin.
        db: The database handle.

    Returns:
        The matchmaker's public profile.

    Raises:
        HTTPException(404): If the matchmaker is not found.
    """
    matchmaker = await matchmaker_repo.get_matchmaker_by_id(db, matchmaker_id)
    if matchmaker is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Matchmaker not found.",
        )
    return _to_out(matchmaker)


@router.patch(
    "/{matchmaker_id}",
    response_model=MatchmakerOut,
    summary="Update a matchmaker's profile",
)
async def update_matchmaker(
    matchmaker_id: str,
    body: MatchmakerUpdate,
    admin: MatchmakerInDB = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> MatchmakerOut:
    """
    Partially update a matchmaker account (admin only).

    Only the fields provided in the request body are modified. If a new
    password is provided, it is hashed before storage.

    Args:
        matchmaker_id: The matchmaker's MongoDB ObjectId.
        body: The fields to update (all optional).
        admin: The authenticated admin.
        db: The database handle.

    Returns:
        The updated matchmaker's public profile.

    Raises:
        HTTPException(404): If the matchmaker is not found.
        HTTPException(409): If the new email conflicts with an existing one.
    """
    # Build the update dict, excluding fields that weren't provided.
    update_data = body.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update.",
        )

    # If a new password was provided, hash it.
    if "password" in update_data:
        plain = update_data.pop("password")
        update_data["password_hash"] = hash_password(plain)

    # If email is being changed, check uniqueness.
    if "email" in update_data and update_data["email"] is not None:
        existing = await matchmaker_repo.get_matchmaker_by_email(
            db, update_data["email"],
        )
        if existing is not None and str(existing.id) != matchmaker_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Email '{update_data['email']}' is already in use.",
            )

    matchmaker = await matchmaker_repo.update_matchmaker(
        db, matchmaker_id, update_data,
    )
    if matchmaker is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Matchmaker not found.",
        )
    return _to_out(matchmaker)


@router.delete(
    "/{matchmaker_id}",
    status_code=status.HTTP_200_OK,
    summary="Deactivate a matchmaker account",
)
async def delete_matchmaker(
    matchmaker_id: str,
    admin: MatchmakerInDB = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    """
    Soft-delete a matchmaker by deactivating their account (admin only).

    The document is not removed from the database — ``is_active`` is set
    to False. The account can be reactivated later via PATCH.

    An admin cannot deactivate their own account (to prevent locking
    everyone out of the system).

    Args:
        matchmaker_id: The matchmaker's MongoDB ObjectId.
        admin: The authenticated admin.
        db: The database handle.

    Returns:
        A confirmation message.

    Raises:
        HTTPException(400): If the admin tries to deactivate themselves.
        HTTPException(404): If the matchmaker is not found.
    """
    # Prevent self-deactivation.
    if str(admin.id) == matchmaker_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate your own account.",
        )

    matchmaker = await matchmaker_repo.deactivate_matchmaker(db, matchmaker_id)
    if matchmaker is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Matchmaker not found.",
        )

    return {"detail": f"Matchmaker '{matchmaker.username}' has been deactivated."}
