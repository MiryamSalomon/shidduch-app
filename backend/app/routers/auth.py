"""
Authentication Router
======================
Handles matchmaker login and identity endpoints.

Endpoints:
    - ``POST /auth/login`` — Authenticate with username + password, receive JWT.
    - ``GET /auth/me`` — Return the currently authenticated matchmaker's profile.

Security features implemented here:
    - **Brute-force protection**: After 10 consecutive failed login attempts,
      the account is locked for 15 minutes. The counter resets on successful
      login.
    - **Constant-time password check**: Even when the username doesn't exist,
      we run a dummy argon2 hash to prevent timing-based username enumeration.
    - **Audit trail**: Every login attempt (success or failure) records the
      timestamp for the ``last_login_at`` / ``locked_until`` fields.

Rate limiting (``slowapi``) is applied at the application level in ``main.py``
and references the ``rate_limit_login`` setting (default: 10 requests/minute/IP).

Design decisions:
    - **No registration endpoint**: Matchmaker accounts are created only by
      admins via ``POST /matchmakers`` or the bootstrap script. This is
      intentional — the system is for a closed team.
    - **No refresh tokens in v1**: An 8-hour access token covers one workday.
      Refresh token rotation adds complexity not justified for ~5 users.
    - **No logout endpoint with token revocation**: Since JWTs are stateless,
      true server-side logout requires a token blocklist (Redis or DB). In v1,
      the frontend simply discards the token. The 8-hour expiry limits the
      window of a stolen token.
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.db import get_db
from app.deps import get_current_matchmaker
from app.limiter import limiter
from app.models.common import MatchmakerRole
from app.models.matchmaker import MatchmakerInDB, MatchmakerOut
from app.repositories import matchmaker_repo
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["Authentication"])

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
# Maximum consecutive failed login attempts before locking the account.
_MAX_FAILED_ATTEMPTS = 10

# How long the account stays locked after exceeding the attempt limit.
_LOCK_DURATION = timedelta(minutes=15)


# ---------------------------------------------------------------------------
# Request / Response Schemas
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    """
    Schema for the login request body.

    Attributes:
        username: The matchmaker's unique login name.
        password: Plain-text password (transmitted over HTTPS, never logged).
    """
    username: str = Field(
        ...,
        min_length=1,
        description="Matchmaker login username",
    )
    password: str = Field(
        ...,
        min_length=1,
        description="Plain-text password",
    )


class LoginResponse(BaseModel):
    """
    Schema for the login response.

    Attributes:
        access_token: The signed JWT string.
        token_type: Always "bearer" — tells the client how to send the
            token (in the ``Authorization: Bearer <token>`` header).
        matchmaker: The authenticated matchmaker's public profile.
    """
    access_token: str
    token_type: str = "bearer"
    matchmaker: MatchmakerOut


class RegisterRequest(BaseModel):
    """
    Schema for the public self-registration request body.

    Public registration always creates accounts with the ``matchmaker`` role —
    never ``admin``. Admin accounts must be promoted manually by an existing
    admin via ``PATCH /matchmakers/{id}``.

    Attributes:
        username: Desired login username (3–50 chars, must be unique).
        display_name: Human-readable name shown in the UI.
        password: Plain-text password (min 8 chars). Hashed before storage.
        email: Optional email; if provided, must be unique.
    """
    username: str = Field(..., min_length=3, max_length=50)
    display_name: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=8, max_length=128)
    email: str | None = Field(default=None)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Authenticate and receive a JWT",
    responses={
        401: {"description": "Invalid credentials"},
        423: {"description": "Account locked due to too many failed attempts"},
        429: {"description": "Rate limit exceeded"},
    },
)
@limiter.limit("10/minute")
async def login(request: Request, body: LoginRequest, db=Depends(get_db)) -> LoginResponse:
    """
    Authenticate a matchmaker with username and password.

    Flow:
        1. Look up the username in the ``matchmakers`` collection.
        2. If not found, run a dummy hash (timing protection) and return 401.
        3. If the account is locked (``locked_until`` > now), return 423.
        4. If the account is inactive, return 401.
        5. Verify the password against the stored argon2id hash.
        6. On failure: increment ``failed_attempts``; if threshold reached,
           set ``locked_until``. Return 401.
        7. On success: reset ``failed_attempts``, update ``last_login_at``,
           create and return a JWT.

    Args:
        body: The login credentials.
        db: MongoDB database handle (injected).

    Returns:
        A LoginResponse containing the JWT and matchmaker profile.
    """
    # ── Step 1: Look up the user ────────────────────────────────────────
    doc = await db["matchmakers"].find_one({"username": body.username})

    if doc is None:
        # Run a dummy hash to prevent timing-based username enumeration.
        # An attacker measuring response time shouldn't be able to tell
        # whether the username exists based on how long the request takes.
        verify_password("dummy_password", "$argon2id$v=19$m=65536,t=3,p=4$dW5rbm93bg$dW5rbm93bg")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )

    matchmaker = MatchmakerInDB(**doc)

    # ── Step 2: Check if account is locked ──────────────────────────────
    if matchmaker.locked_until and matchmaker.locked_until > datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Account locked due to too many failed attempts. "
                   "Try again later.",
        )

    # ── Step 3: Check if account is active ──────────────────────────────
    if not matchmaker.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is disabled. Contact an administrator.",
        )

    # ── Step 4: Verify the password ─────────────────────────────────────
    if not verify_password(body.password, matchmaker.password_hash):
        # Increment the failure counter.
        new_failed = matchmaker.failed_attempts + 1
        update_fields: dict = {
            "failed_attempts": new_failed,
            "updated_at": datetime.utcnow(),
        }

        # If the threshold is reached, lock the account.
        if new_failed >= _MAX_FAILED_ATTEMPTS:
            update_fields["locked_until"] = datetime.utcnow() + _LOCK_DURATION

        await db["matchmakers"].update_one(
            {"_id": matchmaker.id},
            {"$set": update_fields},
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )

    # ── Step 5: Success — reset counters and issue token ────────────────
    now = datetime.utcnow()
    await db["matchmakers"].update_one(
        {"_id": matchmaker.id},
        {
            "$set": {
                "failed_attempts": 0,
                "locked_until": None,
                "last_login_at": now,
                "updated_at": now,
            }
        },
    )

    # Create the JWT with the matchmaker's ObjectId as the subject.
    token = create_access_token(matchmaker_id=str(matchmaker.id))

    # Build the public-safe response.
    matchmaker_out = MatchmakerOut(
        id=str(matchmaker.id),
        username=matchmaker.username,
        display_name=matchmaker.display_name,
        email=matchmaker.email,
        role=matchmaker.role,
        is_active=matchmaker.is_active,
        last_login_at=now,
        created_at=matchmaker.created_at,
    )

    return LoginResponse(
        access_token=token,
        matchmaker=matchmaker_out,
    )


@router.post(
    "/register",
    response_model=LoginResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Public self-registration — create a matchmaker account and log in",
    responses={
        409: {"description": "Username or email already taken"},
        429: {"description": "Rate limit exceeded"},
    },
)
@limiter.limit("5/minute")
async def register(
    request: Request,
    body: RegisterRequest,
    db=Depends(get_db),
) -> LoginResponse:
    """
    Public self-registration endpoint.

    Creates a new account with the ``matchmaker`` role (never admin) and
    returns a JWT so the user is logged in immediately on success.

    Steps:
        1. Verify the username is not taken.
        2. If an email was supplied, verify it is not taken.
        3. Hash the password with argon2id.
        4. Create the matchmaker document.
        5. Issue a JWT access token.

    Args:
        body: The registration payload.
        db: MongoDB database handle (injected).

    Returns:
        A LoginResponse with the JWT and the new matchmaker's public profile.

    Raises:
        HTTPException(409): Username or email already in use.
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

    # ── Build the document ──────────────────────────────────────────────
    data = body.model_dump()
    plain_password = data.pop("password")
    data["password_hash"] = hash_password(plain_password)
    # Public registration is never admin — enforced server-side.
    data["role"] = MatchmakerRole.MATCHMAKER

    matchmaker = await matchmaker_repo.create_matchmaker(db, data)

    # ── Issue JWT and return ────────────────────────────────────────────
    token = create_access_token(matchmaker_id=str(matchmaker.id))

    matchmaker_out = MatchmakerOut(
        id=str(matchmaker.id),
        username=matchmaker.username,
        display_name=matchmaker.display_name,
        email=matchmaker.email,
        role=matchmaker.role,
        is_active=matchmaker.is_active,
        last_login_at=matchmaker.last_login_at,
        created_at=matchmaker.created_at,
    )

    return LoginResponse(
        access_token=token,
        matchmaker=matchmaker_out,
    )


@router.get(
    "/me",
    response_model=MatchmakerOut,
    summary="Get the current authenticated matchmaker",
)
async def get_me(
    current_user: MatchmakerInDB = Depends(get_current_matchmaker),
) -> MatchmakerOut:
    """
    Return the profile of the currently authenticated matchmaker.

    This endpoint is called by the frontend after login (or on page refresh)
    to verify the token is still valid and load the user's profile into
    the auth context.

    Args:
        current_user: The authenticated matchmaker (injected by
            ``get_current_matchmaker`` dependency).

    Returns:
        The matchmaker's public profile (excludes password hash and
        security fields).
    """
    return MatchmakerOut(
        id=str(current_user.id),
        username=current_user.username,
        display_name=current_user.display_name,
        email=current_user.email,
        role=current_user.role,
        is_active=current_user.is_active,
        last_login_at=current_user.last_login_at,
        created_at=current_user.created_at,
    )
