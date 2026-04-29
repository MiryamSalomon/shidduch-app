"""
Candidate CRUD endpoint tests.

Covers:
- Create with valid payload → 201 with computed age
- Create with missing required fields → 422
- List with pagination
- List filters: gender, status, age range, search
- Get by ID → 200 / 404 for nonexistent
- Update (PATCH) — name, status, community
- Soft delete → candidate no longer in active list
- POST /{id}/embed queued without error (OpenAI mocked)
"""

import copy
from unittest.mock import AsyncMock, patch

import pytest

from tests.conftest import VALID_FEMALE_PAYLOAD, VALID_MALE_PAYLOAD


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def create_candidate(client, headers, payload=None):
    if payload is None:
        payload = VALID_MALE_PAYLOAD
    resp = await client.post("/api/v1/candidates", json=payload, headers=headers)
    return resp


# ---------------------------------------------------------------------------
# POST /candidates — create
# ---------------------------------------------------------------------------

async def test_create_candidate_success(http_client, matchmaker_headers):
    resp = await create_candidate(http_client, matchmaker_headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["first_name"] == VALID_MALE_PAYLOAD["first_name"]
    assert body["gender"] == "male"
    assert body["status"] == "active"
    assert body["age"] > 0
    assert "id" in body


async def test_create_candidate_computes_age(http_client, matchmaker_headers):
    resp = await create_candidate(http_client, matchmaker_headers)
    body = resp.json()
    # Born 2000 → must be at least 24 (tests run after 2024)
    assert body["age"] >= 24


async def test_create_candidate_missing_first_name(http_client, matchmaker_headers):
    payload = copy.deepcopy(VALID_MALE_PAYLOAD)
    del payload["first_name"]
    resp = await http_client.post("/api/v1/candidates", json=payload, headers=matchmaker_headers)
    assert resp.status_code == 422


async def test_create_candidate_short_traits(http_client, matchmaker_headers):
    payload = copy.deepcopy(VALID_MALE_PAYLOAD)
    payload["character_traits"] = "Short"  # min_length=10
    resp = await http_client.post("/api/v1/candidates", json=payload, headers=matchmaker_headers)
    assert resp.status_code == 422


async def test_create_candidate_requires_auth(http_client):
    resp = await http_client.post("/api/v1/candidates", json=VALID_MALE_PAYLOAD)
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /candidates — list
# ---------------------------------------------------------------------------

async def test_list_candidates_empty(http_client, matchmaker_headers):
    resp = await http_client.get("/api/v1/candidates", headers=matchmaker_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["items"] == []


async def test_list_candidates_returns_created(http_client, matchmaker_headers):
    await create_candidate(http_client, matchmaker_headers, VALID_MALE_PAYLOAD)
    await create_candidate(http_client, matchmaker_headers, VALID_FEMALE_PAYLOAD)

    resp = await http_client.get("/api/v1/candidates", headers=matchmaker_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 2


async def test_list_filter_by_gender(http_client, matchmaker_headers):
    await create_candidate(http_client, matchmaker_headers, VALID_MALE_PAYLOAD)
    await create_candidate(http_client, matchmaker_headers, VALID_FEMALE_PAYLOAD)

    resp = await http_client.get(
        "/api/v1/candidates", params={"gender": "male"}, headers=matchmaker_headers
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert all(c["gender"] == "male" for c in items)


async def test_list_filter_by_status(http_client, matchmaker_headers):
    await create_candidate(http_client, matchmaker_headers)
    resp = await http_client.get(
        "/api/v1/candidates", params={"status": "active"}, headers=matchmaker_headers
    )
    assert resp.json()["total"] >= 1


async def test_list_search_by_name(http_client, matchmaker_headers):
    await create_candidate(http_client, matchmaker_headers, VALID_MALE_PAYLOAD)
    await create_candidate(http_client, matchmaker_headers, VALID_FEMALE_PAYLOAD)

    resp = await http_client.get(
        "/api/v1/candidates", params={"search": "Rivka"}, headers=matchmaker_headers
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["first_name"] == "Rivka"


async def test_list_age_range_filter(http_client, matchmaker_headers):
    await create_candidate(http_client, matchmaker_headers, VALID_MALE_PAYLOAD)   # age ~24
    await create_candidate(http_client, matchmaker_headers, VALID_FEMALE_PAYLOAD)  # age ~22

    resp = await http_client.get(
        "/api/v1/candidates",
        params={"age_min": 23, "age_max": 25},
        headers=matchmaker_headers,
    )
    items = resp.json()["items"]
    assert all(23 <= c["age"] <= 25 for c in items)


async def test_list_pagination(http_client, matchmaker_headers):
    # Create 3 candidates
    for i in range(3):
        payload = copy.deepcopy(VALID_MALE_PAYLOAD)
        payload["first_name"] = f"Yosef{i}"
        payload["last_name"] = f"Cohen{i}"
        await create_candidate(http_client, matchmaker_headers, payload)

    resp = await http_client.get(
        "/api/v1/candidates", params={"page": 1, "page_size": 2}, headers=matchmaker_headers
    )
    body = resp.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2
    assert body["total_pages"] == 2


# ---------------------------------------------------------------------------
# GET /candidates/{id}
# ---------------------------------------------------------------------------

async def test_get_candidate_by_id(http_client, matchmaker_headers):
    created = (await create_candidate(http_client, matchmaker_headers)).json()
    resp = await http_client.get(
        f"/api/v1/candidates/{created['id']}", headers=matchmaker_headers
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


async def test_get_candidate_not_found(http_client, matchmaker_headers):
    resp = await http_client.get(
        "/api/v1/candidates/000000000000000000000000", headers=matchmaker_headers
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /candidates/{id}
# ---------------------------------------------------------------------------

async def test_update_candidate_name(http_client, matchmaker_headers):
    created = (await create_candidate(http_client, matchmaker_headers)).json()
    resp = await http_client.patch(
        f"/api/v1/candidates/{created['id']}",
        json={"first_name": "Menachem"},
        headers=matchmaker_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["first_name"] == "Menachem"


async def test_update_candidate_status(http_client, matchmaker_headers):
    created = (await create_candidate(http_client, matchmaker_headers)).json()
    resp = await http_client.patch(
        f"/api/v1/candidates/{created['id']}",
        json={"status": "paused"},
        headers=matchmaker_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "paused"


async def test_update_candidate_not_found(http_client, matchmaker_headers):
    resp = await http_client.patch(
        "/api/v1/candidates/000000000000000000000000",
        json={"first_name": "Nobody"},
        headers=matchmaker_headers,
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /candidates/{id}
# ---------------------------------------------------------------------------

async def test_delete_candidate(http_client, matchmaker_headers):
    created = (await create_candidate(http_client, matchmaker_headers)).json()
    cid = created["id"]

    del_resp = await http_client.delete(
        f"/api/v1/candidates/{cid}", headers=matchmaker_headers
    )
    assert del_resp.status_code == 200

    # Soft-delete sets status to "archived" — verify via GET
    get_resp = await http_client.get(f"/api/v1/candidates/{cid}", headers=matchmaker_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["status"] == "archived"

    # Archived candidate must not appear when filtering by active status
    list_resp = await http_client.get(
        "/api/v1/candidates", params={"status": "active"}, headers=matchmaker_headers
    )
    ids = [c["id"] for c in list_resp.json()["items"]]
    assert cid not in ids


async def test_delete_candidate_not_found(http_client, matchmaker_headers):
    resp = await http_client.delete(
        "/api/v1/candidates/000000000000000000000000", headers=matchmaker_headers
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /candidates/{id}/embed
# ---------------------------------------------------------------------------

async def test_trigger_embed_queued(http_client, matchmaker_headers):
    created = (await create_candidate(http_client, matchmaker_headers)).json()

    with patch("app.routers.candidates.embeddings.embed_candidate", new=AsyncMock()):
        resp = await http_client.post(
            f"/api/v1/candidates/{created['id']}/embed",
            headers=matchmaker_headers,
        )
    assert resp.status_code == 200


async def test_trigger_embed_not_found(http_client, matchmaker_headers):
    with patch("app.routers.candidates.embeddings.embed_candidate", new=AsyncMock()):
        resp = await http_client.post(
            "/api/v1/candidates/000000000000000000000000/embed",
            headers=matchmaker_headers,
        )
    assert resp.status_code == 404
