"""
Suggestion lifecycle endpoint tests.

Covers:
- Create with valid male/female pair → 201
- Create with wrong-gender candidate → 422
- Create with archived candidate → 422
- Create duplicate pair → 409
- Get suggestion → 200 / 404
- Update status → history entry appended
- List with status / source / candidate_id filters
- Delete (admin) → 200 / (non-admin) → 403
"""

import pytest

from tests.conftest import VALID_FEMALE_PAYLOAD, VALID_MALE_PAYLOAD


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def create_candidate(client, headers, payload):
    resp = await client.post("/api/v1/candidates", json=payload, headers=headers)
    assert resp.status_code == 201
    return resp.json()["id"]


async def create_suggestion(client, headers, male_id: str, female_id: str, note=None):
    body = {"candidate_male_id": male_id, "candidate_female_id": female_id}
    if note:
        body["note"] = note
    return await client.post("/api/v1/suggestions", json=body, headers=headers)


# ---------------------------------------------------------------------------
# POST /suggestions
# ---------------------------------------------------------------------------

async def test_create_suggestion_success(http_client, matchmaker_headers):
    male_id = await create_candidate(http_client, matchmaker_headers, VALID_MALE_PAYLOAD)
    female_id = await create_candidate(http_client, matchmaker_headers, VALID_FEMALE_PAYLOAD)

    resp = await create_suggestion(http_client, matchmaker_headers, male_id, female_id, note="Good match")
    assert resp.status_code == 201
    body = resp.json()
    assert body["candidate_male_id"] == male_id
    assert body["candidate_female_id"] == female_id
    assert body["source"] == "manual"
    assert body["status"] == "proposed"


async def test_create_suggestion_wrong_gender_male_slot(http_client, matchmaker_headers):
    """Putting a female candidate in the male slot should fail."""
    female_id = await create_candidate(http_client, matchmaker_headers, VALID_FEMALE_PAYLOAD)
    male_id = await create_candidate(http_client, matchmaker_headers, VALID_MALE_PAYLOAD)

    resp = await create_suggestion(http_client, matchmaker_headers, female_id, male_id)
    assert resp.status_code == 422


async def test_create_suggestion_archived_candidate(http_client, matchmaker_headers):
    male_id = await create_candidate(http_client, matchmaker_headers, VALID_MALE_PAYLOAD)
    female_id = await create_candidate(http_client, matchmaker_headers, VALID_FEMALE_PAYLOAD)

    # Archive the male candidate
    await http_client.patch(
        f"/api/v1/candidates/{male_id}",
        json={"status": "archived"},
        headers=matchmaker_headers,
    )

    resp = await create_suggestion(http_client, matchmaker_headers, male_id, female_id)
    assert resp.status_code == 422


async def test_create_suggestion_duplicate_pair(http_client, matchmaker_headers):
    male_id = await create_candidate(http_client, matchmaker_headers, VALID_MALE_PAYLOAD)
    female_id = await create_candidate(http_client, matchmaker_headers, VALID_FEMALE_PAYLOAD)

    resp1 = await create_suggestion(http_client, matchmaker_headers, male_id, female_id)
    assert resp1.status_code == 201

    resp2 = await create_suggestion(http_client, matchmaker_headers, male_id, female_id)
    assert resp2.status_code == 409


async def test_create_suggestion_invalid_candidate_id(http_client, matchmaker_headers):
    resp = await create_suggestion(
        http_client, matchmaker_headers,
        "000000000000000000000000",
        "000000000000000000000001",
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /suggestions/{id}
# ---------------------------------------------------------------------------

async def test_get_suggestion_by_id(http_client, matchmaker_headers):
    male_id = await create_candidate(http_client, matchmaker_headers, VALID_MALE_PAYLOAD)
    female_id = await create_candidate(http_client, matchmaker_headers, VALID_FEMALE_PAYLOAD)
    created = (await create_suggestion(http_client, matchmaker_headers, male_id, female_id)).json()

    resp = await http_client.get(
        f"/api/v1/suggestions/{created['id']}", headers=matchmaker_headers
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


async def test_get_suggestion_not_found(http_client, matchmaker_headers):
    resp = await http_client.get(
        "/api/v1/suggestions/000000000000000000000000", headers=matchmaker_headers
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /suggestions/{id} — status update
# ---------------------------------------------------------------------------

async def test_update_suggestion_status(http_client, matchmaker_headers):
    male_id = await create_candidate(http_client, matchmaker_headers, VALID_MALE_PAYLOAD)
    female_id = await create_candidate(http_client, matchmaker_headers, VALID_FEMALE_PAYLOAD)
    created = (await create_suggestion(http_client, matchmaker_headers, male_id, female_id)).json()

    resp = await http_client.patch(
        f"/api/v1/suggestions/{created['id']}",
        json={"status": "reviewing", "note": "Looks promising"},
        headers=matchmaker_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "reviewing"


async def test_update_suggestion_appends_history(http_client, matchmaker_headers):
    male_id = await create_candidate(http_client, matchmaker_headers, VALID_MALE_PAYLOAD)
    female_id = await create_candidate(http_client, matchmaker_headers, VALID_FEMALE_PAYLOAD)
    created = (await create_suggestion(http_client, matchmaker_headers, male_id, female_id)).json()

    # Move through two status transitions
    await http_client.patch(
        f"/api/v1/suggestions/{created['id']}",
        json={"status": "reviewing"},
        headers=matchmaker_headers,
    )
    resp = await http_client.patch(
        f"/api/v1/suggestions/{created['id']}",
        json={"status": "contacted", "note": "Called the family"},
        headers=matchmaker_headers,
    )
    history = resp.json()["history"]
    # create_suggestion adds initial "proposed" entry → 2 patches = 3 total
    assert len(history) == 3
    assert history[-1]["status"] == "contacted"
    assert history[-1]["note"] == "Called the family"


# ---------------------------------------------------------------------------
# GET /suggestions — list
# ---------------------------------------------------------------------------

async def test_list_suggestions_empty(http_client, matchmaker_headers):
    resp = await http_client.get("/api/v1/suggestions", headers=matchmaker_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


async def test_list_suggestions_with_data(http_client, matchmaker_headers):
    male_id = await create_candidate(http_client, matchmaker_headers, VALID_MALE_PAYLOAD)
    female_id = await create_candidate(http_client, matchmaker_headers, VALID_FEMALE_PAYLOAD)
    await create_suggestion(http_client, matchmaker_headers, male_id, female_id)

    resp = await http_client.get("/api/v1/suggestions", headers=matchmaker_headers)
    assert resp.json()["total"] == 1


async def test_list_suggestions_filter_by_status(http_client, matchmaker_headers):
    male_id = await create_candidate(http_client, matchmaker_headers, VALID_MALE_PAYLOAD)
    female_id = await create_candidate(http_client, matchmaker_headers, VALID_FEMALE_PAYLOAD)
    created = (await create_suggestion(http_client, matchmaker_headers, male_id, female_id)).json()

    await http_client.patch(
        f"/api/v1/suggestions/{created['id']}",
        json={"status": "contacted"},
        headers=matchmaker_headers,
    )

    resp_proposed = await http_client.get(
        "/api/v1/suggestions", params={"status": "proposed"}, headers=matchmaker_headers
    )
    assert resp_proposed.json()["total"] == 0

    resp_contacted = await http_client.get(
        "/api/v1/suggestions", params={"status": "contacted"}, headers=matchmaker_headers
    )
    assert resp_contacted.json()["total"] == 1


async def test_list_suggestions_filter_by_candidate_id(http_client, matchmaker_headers):
    male_id = await create_candidate(http_client, matchmaker_headers, VALID_MALE_PAYLOAD)
    female_id = await create_candidate(http_client, matchmaker_headers, VALID_FEMALE_PAYLOAD)
    await create_suggestion(http_client, matchmaker_headers, male_id, female_id)

    resp = await http_client.get(
        "/api/v1/suggestions", params={"candidate_id": male_id}, headers=matchmaker_headers
    )
    assert resp.json()["total"] == 1

    resp2 = await http_client.get(
        "/api/v1/suggestions", params={"candidate_id": female_id}, headers=matchmaker_headers
    )
    assert resp2.json()["total"] == 1


async def test_list_suggestions_filter_source_manual(http_client, matchmaker_headers):
    male_id = await create_candidate(http_client, matchmaker_headers, VALID_MALE_PAYLOAD)
    female_id = await create_candidate(http_client, matchmaker_headers, VALID_FEMALE_PAYLOAD)
    await create_suggestion(http_client, matchmaker_headers, male_id, female_id)

    resp = await http_client.get(
        "/api/v1/suggestions", params={"source": "manual"}, headers=matchmaker_headers
    )
    assert resp.json()["total"] == 1

    resp_ai = await http_client.get(
        "/api/v1/suggestions", params={"source": "ai"}, headers=matchmaker_headers
    )
    assert resp_ai.json()["total"] == 0


# ---------------------------------------------------------------------------
# DELETE /suggestions/{id}
# ---------------------------------------------------------------------------

async def test_delete_suggestion_admin(http_client, admin_headers, matchmaker_headers):
    male_id = await create_candidate(http_client, matchmaker_headers, VALID_MALE_PAYLOAD)
    female_id = await create_candidate(http_client, matchmaker_headers, VALID_FEMALE_PAYLOAD)
    created = (await create_suggestion(http_client, matchmaker_headers, male_id, female_id)).json()

    resp = await http_client.delete(
        f"/api/v1/suggestions/{created['id']}", headers=admin_headers
    )
    assert resp.status_code == 200

    get_resp = await http_client.get(
        f"/api/v1/suggestions/{created['id']}", headers=admin_headers
    )
    assert get_resp.status_code == 404


async def test_delete_suggestion_non_admin_forbidden(http_client, matchmaker_headers):
    male_id = await create_candidate(http_client, matchmaker_headers, VALID_MALE_PAYLOAD)
    female_id = await create_candidate(http_client, matchmaker_headers, VALID_FEMALE_PAYLOAD)
    created = (await create_suggestion(http_client, matchmaker_headers, male_id, female_id)).json()

    resp = await http_client.delete(
        f"/api/v1/suggestions/{created['id']}", headers=matchmaker_headers
    )
    assert resp.status_code == 403
