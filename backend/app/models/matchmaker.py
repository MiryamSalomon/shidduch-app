"""
Matchmaker Models
==================
Pydantic schemas for the ``matchmakers`` collection — the users of this system.

Each matchmaker (shadchan) has their own login credentials and role. All
matchmakers share the same candidate pool, but the audit log tracks which
matchmaker performed each action.

Three model layers:
    - **MatchmakerCreate** — what the API accepts when creating a new matchmaker.
    - **MatchmakerInDB** — the full document as stored in MongoDB (includes
      password hash, never exposed via API).
    - **MatchmakerOut** — what the API returns to the client (excludes secrets).

This separation ensures the password hash never leaks into an API response,
even if a developer accidentally returns the wrong model type.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.common import MatchmakerRole, MongoBaseModel


class MatchmakerCreate(BaseModel):
    """
    Schema for creating a new matchmaker account.

    Accepted by ``POST /api/v1/matchmakers`` (admin-only endpoint).

    Attributes:
        username: Unique login name. Used in the JWT ``sub`` claim.
        display_name: Human-readable name shown in the UI and audit log
            (e.g. "הרב כהן" or "Rabbi Cohen").
        email: Optional email address. Unique if provided.
        password: Plain-text password. Will be hashed with argon2id before
            storage — never stored as-is.
        role: Either ``admin`` (can manage users, view audit) or ``matchmaker``
            (standard access). Defaults to ``matchmaker``.
    """

    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="Unique login username",
    )
    display_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Display name shown in the UI",
    )
    email: str | None = Field(
        default=None,
        description="Optional email address",
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Plain-text password (will be hashed before storage)",
    )
    role: MatchmakerRole = Field(
        default=MatchmakerRole.MATCHMAKER,
        description="User role: admin or matchmaker",
    )


class MatchmakerInDB(MongoBaseModel):
    """
    Full matchmaker document as stored in MongoDB.

    This model is used internally by repositories and services. It includes
    the ``password_hash`` and brute-force protection fields that must never
    be returned to the client.

    Attributes:
        username: Unique login name.
        display_name: Human-readable display name.
        email: Optional email (unique if set).
        password_hash: Argon2id hash of the password.
        role: User role (admin or matchmaker).
        is_active: Whether the account is enabled. Disabled accounts cannot
            log in but are not deleted (for audit trail integrity).
        failed_attempts: Number of consecutive failed login attempts.
            Reset to 0 on successful login.
        locked_until: If set, the account is locked until this timestamp
            due to too many failed attempts (brute-force protection).
        last_login_at: Timestamp of the most recent successful login.
    """

    username: str
    display_name: str
    email: str | None = None
    password_hash: str
    role: MatchmakerRole = MatchmakerRole.MATCHMAKER
    is_active: bool = True
    failed_attempts: int = 0
    locked_until: datetime | None = None
    last_login_at: datetime | None = None


class MatchmakerOut(BaseModel):
    """
    Matchmaker data returned by the API to the client.

    Excludes sensitive fields: ``password_hash``, ``failed_attempts``,
    ``locked_until``. These are internal security fields that the frontend
    has no reason to see.

    Attributes:
        id: MongoDB document ID as a string.
        username: Login username.
        display_name: Human-readable display name.
        email: Optional email address.
        role: User role.
        is_active: Whether the account is enabled.
        last_login_at: When the user last logged in.
        created_at: When the account was created.
    """

    id: str = Field(..., description="Matchmaker ID")
    username: str
    display_name: str
    email: str | None = None
    role: MatchmakerRole
    is_active: bool
    last_login_at: datetime | None = None
    created_at: datetime


class MatchmakerUpdate(BaseModel):
    """
    Schema for partially updating a matchmaker account.

    All fields are optional — only provided fields are updated.
    Used by ``PATCH /api/v1/matchmakers/{id}`` (admin-only).

    Attributes:
        display_name: New display name.
        email: New email address.
        password: New plain-text password (will be re-hashed).
        role: New role.
        is_active: Enable or disable the account.
    """

    display_name: str | None = None
    email: str | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)
    role: MatchmakerRole | None = None
    is_active: bool | None = None
