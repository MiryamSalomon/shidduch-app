"""
FastAPI Dependencies
=====================
Reusable dependency functions injected into route handlers via ``Depends()``.

The main dependency here is ``get_current_matchmaker`` — it extracts the JWT
from the ``Authorization`` header, verifies it, loads the matchmaker from
MongoDB, and checks that the account is active. Every authenticated endpoint
depends on this.

Why a separate module?
    Putting dependencies in their own file avoids circular imports.
    Routes import from ``deps``, and ``deps`` imports from ``db`` and
    ``security`` — neither of which imports from routes. Clean DAG.

Dependency chain::

    Request
      → get_current_matchmaker()
          → decode_access_token() (from security.py)
          → db["matchmakers"].find_one() (from db.py)
      → route handler receives MatchmakerInDB

Usage in routers::

    from fastapi import Depends
    from app.deps import get_current_matchmaker
    from app.models import MatchmakerInDB

    @router.get("/candidates")
    async def list_candidates(
        current_user: MatchmakerInDB = Depends(get_current_matchmaker),
    ):
        ...
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.db import get_db
from app.models.matchmaker import MatchmakerInDB
from app.security import decode_access_token

# ---------------------------------------------------------------------------
# Bearer Token Extraction
# ---------------------------------------------------------------------------
# HTTPBearer is a FastAPI security scheme that reads the ``Authorization``
# header, expects the format ``Bearer <token>``, and extracts the token
# string. If the header is missing or malformed, it returns a 403 by default.
# We set ``auto_error=False`` so we can return a more specific 401 ourselves.
_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_matchmaker(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db=Depends(get_db),
) -> MatchmakerInDB:
    """
    FastAPI dependency that authenticates the current request.

    Performs three sequential checks:

    1. **Token present?** — The ``Authorization: Bearer <token>`` header
       must be present. If missing, return 401.

    2. **Token valid?** — The JWT must have a valid signature and must not
       be expired. If invalid, return 401.

    3. **Account active?** — The matchmaker referenced by the token's
       ``sub`` claim must exist in the database and have ``is_active=True``.
       If not found or inactive, return 401.

    If all checks pass, returns the full ``MatchmakerInDB`` document,
    which the route handler can use for:
        - Authorisation checks (e.g. ``current_user.role == "admin"``).
        - Audit logging (``current_user.id`` as the actor).

    Args:
        credentials: Extracted automatically by FastAPI from the
            ``Authorization: Bearer`` header. None if header is missing.
        db: The MongoDB database handle (injected by ``get_db``).

    Returns:
        The authenticated matchmaker's full database document.

    Raises:
        HTTPException(401): If authentication fails at any step.
    """
    # ── Step 1: Check that a Bearer token was provided ──────────────────
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Provide a Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # ── Step 2: Decode and verify the JWT ───────────────────────────────
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # The ``sub`` claim contains the matchmaker's MongoDB ObjectId as a string.
    matchmaker_id = payload.get("sub")
    if matchmaker_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject claim.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # ── Step 3: Load the matchmaker from the database ───────────────────
    from bson import ObjectId

    doc = await db["matchmakers"].find_one({"_id": ObjectId(matchmaker_id)})
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Matchmaker account not found.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    matchmaker = MatchmakerInDB(**doc)

    # ── Step 4: Check that the account is active ────────────────────────
    if not matchmaker.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is disabled. Contact an administrator.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return matchmaker


async def require_admin(
    current_user: MatchmakerInDB = Depends(get_current_matchmaker),
) -> MatchmakerInDB:
    """
    FastAPI dependency that requires the current user to be an admin.

    Chains on top of ``get_current_matchmaker`` — first authenticates,
    then checks the role. Used by admin-only endpoints like
    ``POST /matchmakers`` and ``GET /audit``.

    Args:
        current_user: The authenticated matchmaker (injected by
            ``get_current_matchmaker``).

    Returns:
        The authenticated admin matchmaker.

    Raises:
        HTTPException(403): If the user is authenticated but not an admin.
    """
    if current_user.role.value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required.",
        )
    return current_user
