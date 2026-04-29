"""
Shared test fixtures for the Shidduch backend test suite.

All tests run against an in-memory MongoDB (mongomock-motor) — no real
database or network is needed. The FastAPI lifespan (connect_db / close_db)
is mocked so tests do not attempt to reach a real MongoDB instance.
"""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient

from app.db import get_db
from app.limiter import limiter
from app.main import app
from app.security import hash_password

# ---------------------------------------------------------------------------
# Rate limiter reset (prevents bleed between tests)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Clear slowapi's in-memory counters before each test."""
    try:
        limiter._limiter.storage.reset()
    except Exception:
        pass
    yield


# ---------------------------------------------------------------------------
# In-memory database
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db():
    """Fresh in-memory MongoDB for each test function."""
    client = AsyncMongoMockClient()
    return client["test_shidduch"]


# ---------------------------------------------------------------------------
# HTTP test client
# ---------------------------------------------------------------------------

@pytest.fixture
async def http_client(mock_db):
    """
    httpx AsyncClient wired to the FastAPI app with the mock DB injected.
    The lifespan (connect_db / close_db) is patched to no-ops so the test
    does not try to reach a real MongoDB instance.
    """
    app.dependency_overrides[get_db] = lambda: mock_db

    with (
        patch("app.db.connect_db", new=AsyncMock()),
        patch("app.db.close_db", new=AsyncMock()),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            yield client

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# User fixtures
# ---------------------------------------------------------------------------

def _make_user_doc(username: str, password: str, role: str, display_name: str) -> dict:
    now = datetime.utcnow()
    return {
        "username": username,
        "display_name": display_name,
        "email": None,
        "password_hash": hash_password(password),
        "role": role,
        "is_active": True,
        "failed_attempts": 0,
        "locked_until": None,
        "last_login_at": None,
        "created_at": now,
        "updated_at": now,
    }


@pytest.fixture
async def admin_user(mock_db):
    doc = _make_user_doc("testadmin", "adminpass1", "admin", "Test Admin")
    result = await mock_db["matchmakers"].insert_one(doc)
    return {"id": str(result.inserted_id), "username": "testadmin", "password": "adminpass1"}


@pytest.fixture
async def matchmaker_user(mock_db):
    doc = _make_user_doc("testmatchmaker", "mmpass123", "matchmaker", "Test Matchmaker")
    result = await mock_db["matchmakers"].insert_one(doc)
    return {"id": str(result.inserted_id), "username": "testmatchmaker", "password": "mmpass123"}


# ---------------------------------------------------------------------------
# Auth header fixtures
# ---------------------------------------------------------------------------

async def _login(client, username: str, password: str) -> dict:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture
async def admin_headers(http_client, admin_user):
    return await _login(http_client, admin_user["username"], admin_user["password"])


@pytest.fixture
async def matchmaker_headers(http_client, matchmaker_user):
    return await _login(http_client, matchmaker_user["username"], matchmaker_user["password"])


# ---------------------------------------------------------------------------
# Candidate factory
# ---------------------------------------------------------------------------

VALID_MALE_PAYLOAD = {
    "first_name": "Yosef",
    "last_name": "Cohen",
    "gender": "male",
    "date_of_birth": "2000-03-15",
    "city": "Jerusalem",
    "community": "litvish",
    "education": {
        "current_institution": "Mir Yeshiva",
        "current_study": None,
        "previous_institutions": [],
    },
    "family": {
        "father_profession": "Rosh Yeshiva",
        "mother_profession": "Teacher",
        "siblings": [],
        "num_brothers": 0,
        "num_sisters": 0,
    },
    "character_traits": "Serious learner, kind and thoughtful, deeply dedicated to Torah study.",
    "preferences": "Looking for a serious girl from a good family who values Torah learning.",
}

VALID_FEMALE_PAYLOAD = {
    "first_name": "Rivka",
    "last_name": "Levi",
    "gender": "female",
    "date_of_birth": "2002-07-20",
    "city": "Bnei Brak",
    "community": "litvish",
    "education": {
        "current_institution": "Beth Jacob Seminary",
        "current_study": "Education",
        "previous_institutions": [],
    },
    "family": {
        "father_profession": "Rabbi",
        "mother_profession": "Nurse",
        "siblings": [],
        "num_brothers": 0,
        "num_sisters": 0,
    },
    "character_traits": "Warm, caring, dedicated to chesed, loves learning and growth.",
    "preferences": "Looking for a serious learner who is kind and family-oriented.",
}
