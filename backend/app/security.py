"""
Security Utilities
===================
Password hashing and JWT token management for the authentication system.

This module contains two distinct security concerns:

1. **Password hashing** — Uses argon2id (via ``argon2-cffi``) to hash and
   verify passwords. Argon2id is the winner of the Password Hashing
   Competition and is recommended by OWASP. Unlike bcrypt, it has no
   72-byte password truncation limit, and it is resistant to both
   side-channel (timing) and GPU/ASIC brute-force attacks.

2. **JWT tokens** — Uses python-jose to create and verify HS256 JSON Web
   Tokens. Each token contains the matchmaker's MongoDB ``_id`` as the
   ``sub`` (subject) claim, plus standard ``exp`` (expiration) and ``iat``
   (issued-at) claims.

Design decisions:
    - **HS256 (symmetric)**: Simpler than RS256 for a single-backend system.
      The same ``JWT_SECRET`` signs and verifies — no key distribution needed.
    - **No refresh tokens in v1**: A single 8-hour access token covers one
      workday. The matchmaker logs in each morning. Refresh tokens add
      complexity (rotation, revocation) that isn't justified for a small team.
    - **``sub`` is the ObjectId string**: This lets ``deps.py`` look up the
      matchmaker directly by ``_id`` without a username→id query.

Usage::

    from app.security import hash_password, verify_password, create_access_token

    hashed = hash_password("my_secure_password")
    assert verify_password("my_secure_password", hashed)

    token = create_access_token(matchmaker_id="665f1a2b3c4d5e6f7a8b9c0d")
"""

from datetime import datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from jose import JWTError, jwt

from app.config import get_settings

# ---------------------------------------------------------------------------
# Password Hashing
# ---------------------------------------------------------------------------
# A single PasswordHasher instance is reused across the application.
# The default argon2id parameters (time_cost=3, memory_cost=65536 KB,
# parallelism=4) provide strong security for a server-side application.
# These can be tuned via PasswordHasher constructor args if needed.
_hasher = PasswordHasher()


def hash_password(plain_password: str) -> str:
    """
    Hash a plain-text password using argon2id.

    The returned string contains the algorithm parameters, salt, and hash
    in the standard PHC string format::

        $argon2id$v=19$m=65536,t=3,p=4$<salt>$<hash>

    This means the salt and parameters are self-contained in the hash —
    no separate salt column is needed in the database.

    Args:
        plain_password: The user's plain-text password.

    Returns:
        The argon2id hash string (PHC format).
    """
    return _hasher.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain-text password against a stored argon2id hash.

    Uses constant-time comparison internally (provided by argon2-cffi)
    to prevent timing attacks.

    If the hash was created with older parameters, argon2-cffi's
    ``check_needs_rehash()`` can be used separately to trigger a
    re-hash on next login — not implemented in v1 but the foundation
    is here.

    Args:
        plain_password: The password the user typed in the login form.
        hashed_password: The stored hash from the database.

    Returns:
        True if the password matches, False otherwise.
    """
    try:
        return _hasher.verify(hashed_password, plain_password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


# ---------------------------------------------------------------------------
# JWT Token Management
# ---------------------------------------------------------------------------

# The algorithm used for signing. HS256 = HMAC-SHA256 (symmetric).
_ALGORITHM = "HS256"


def create_access_token(matchmaker_id: str) -> str:
    """
    Create a signed JWT access token for a matchmaker.

    The token payload contains:
        - ``sub``: The matchmaker's MongoDB ObjectId as a string.
          This is the standard JWT subject claim.
        - ``exp``: Expiration timestamp (UTC). After this time, the token
          is rejected automatically by ``decode_access_token()``.
        - ``iat``: Issued-at timestamp (UTC). Useful for audit/debugging.

    The token is signed with the ``JWT_SECRET`` from settings using HS256.

    Args:
        matchmaker_id: The matchmaker's MongoDB ``_id`` as a hex string.

    Returns:
        A signed JWT string (three base64url-encoded parts separated by dots).
    """
    settings = get_settings()
    now = datetime.utcnow()

    payload = {
        "sub": matchmaker_id,
        "exp": now + timedelta(hours=settings.jwt_expiry_hours),
        "iat": now,
    }

    return jwt.encode(payload, settings.jwt_secret, algorithm=_ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    """
    Decode and verify a JWT access token.

    Validates the signature (using ``JWT_SECRET``) and checks that the
    token has not expired (``exp`` claim). If either check fails, returns
    None instead of raising — the caller (``deps.py``) converts this to
    an HTTP 401.

    Args:
        token: The raw JWT string from the ``Authorization: Bearer`` header.

    Returns:
        The decoded payload dict (with ``sub``, ``exp``, ``iat`` keys)
        if the token is valid, or None if it's invalid/expired.
    """
    try:
        settings = get_settings()
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[_ALGORITHM],
        )
        return payload
    except JWTError:
        return None
