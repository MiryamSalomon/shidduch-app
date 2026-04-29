"""
Authentication endpoint tests.

Covers:
- Successful login → JWT returned
- Wrong username / wrong password → 401
- Inactive account → 401
- Locked account → 423
- GET /auth/me with valid / invalid / missing token
- Brute-force counter increments and account locks at threshold
"""

from datetime import datetime, timedelta

import pytest

from app.security import hash_password


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------

async def test_login_success(http_client, admin_user):
    resp = await http_client.post(
        "/api/v1/auth/login",
        json={"username": admin_user["username"], "password": admin_user["password"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert body["matchmaker"]["username"] == admin_user["username"]
    assert body["matchmaker"]["role"] == "admin"


async def test_login_wrong_password(http_client, admin_user):
    resp = await http_client.post(
        "/api/v1/auth/login",
        json={"username": admin_user["username"], "password": "wrong"},
    )
    assert resp.status_code == 401


async def test_login_unknown_user(http_client):
    resp = await http_client.post(
        "/api/v1/auth/login",
        json={"username": "nobody", "password": "irrelevant"},
    )
    assert resp.status_code == 401


async def test_login_inactive_account(http_client, mock_db):
    from datetime import datetime
    now = datetime.utcnow()
    await mock_db["matchmakers"].insert_one({
        "username": "inactive",
        "display_name": "Inactive User",
        "email": None,
        "password_hash": hash_password("pass12345"),
        "role": "matchmaker",
        "is_active": False,
        "failed_attempts": 0,
        "locked_until": None,
        "last_login_at": None,
        "created_at": now,
        "updated_at": now,
    })
    resp = await http_client.post(
        "/api/v1/auth/login",
        json={"username": "inactive", "password": "pass12345"},
    )
    assert resp.status_code == 401


async def test_login_locked_account(http_client, mock_db):
    now = datetime.utcnow()
    await mock_db["matchmakers"].insert_one({
        "username": "locked",
        "display_name": "Locked User",
        "email": None,
        "password_hash": hash_password("pass12345"),
        "role": "matchmaker",
        "is_active": True,
        "failed_attempts": 10,
        "locked_until": now + timedelta(minutes=10),
        "last_login_at": None,
        "created_at": now,
        "updated_at": now,
    })
    resp = await http_client.post(
        "/api/v1/auth/login",
        json={"username": "locked", "password": "pass12345"},
    )
    assert resp.status_code == 423


async def test_login_increments_failed_attempts(http_client, admin_user, mock_db):
    await http_client.post(
        "/api/v1/auth/login",
        json={"username": admin_user["username"], "password": "wrongpass"},
    )
    doc = await mock_db["matchmakers"].find_one({"username": admin_user["username"]})
    assert doc["failed_attempts"] == 1


async def test_login_resets_failed_attempts_on_success(http_client, admin_user, mock_db):
    # Simulate some prior failed attempts
    await mock_db["matchmakers"].update_one(
        {"username": admin_user["username"]},
        {"$set": {"failed_attempts": 5}},
    )
    resp = await http_client.post(
        "/api/v1/auth/login",
        json={"username": admin_user["username"], "password": admin_user["password"]},
    )
    assert resp.status_code == 200
    doc = await mock_db["matchmakers"].find_one({"username": admin_user["username"]})
    assert doc["failed_attempts"] == 0


async def test_login_locks_after_threshold(http_client, admin_user, mock_db):
    # Pre-set to one below the threshold
    await mock_db["matchmakers"].update_one(
        {"username": admin_user["username"]},
        {"$set": {"failed_attempts": 9}},
    )
    resp = await http_client.post(
        "/api/v1/auth/login",
        json={"username": admin_user["username"], "password": "wrongpass"},
    )
    assert resp.status_code == 401
    doc = await mock_db["matchmakers"].find_one({"username": admin_user["username"]})
    assert doc["locked_until"] is not None


# ---------------------------------------------------------------------------
# GET /auth/me
# ---------------------------------------------------------------------------

async def test_get_me_success(http_client, admin_headers, admin_user):
    resp = await http_client.get("/api/v1/auth/me", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["username"] == admin_user["username"]


async def test_get_me_no_token(http_client):
    resp = await http_client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_get_me_invalid_token(http_client):
    resp = await http_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer this.is.garbage"},
    )
    assert resp.status_code == 401
