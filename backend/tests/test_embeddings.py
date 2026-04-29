"""
Embedding service unit tests.

Tests the embedding service functions directly (no HTTP layer), with the
OpenAI client mocked. Covers:

- build_profile_text() includes expected fields
- build_preferences_text() contains the preferences string
- embed_candidate() calls the OpenAI API and stores the result
- embed_candidate() skips re-embedding when text hash is unchanged
- embed_candidate() re-embeds when force=True regardless of hash
- embed_candidates_bulk() processes all candidates without embeddings
"""

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest
from mongomock_motor import AsyncMongoMockClient

from app.models.candidate import CandidateInDB, Education, Family
from app.models.common import CandidateStatus, Community, Gender
from app.services.embeddings import (
    build_preferences_text,
    build_profile_text,
    embed_candidate,
    embed_candidates_bulk,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def test_db():
    client = AsyncMongoMockClient()
    return client["test_embed"]


def _make_candidate(**overrides) -> CandidateInDB:
    from bson import ObjectId
    defaults = {
        "id": ObjectId(),
        "first_name": "Yosef",
        "last_name": "Cohen",
        "gender": Gender.MALE,
        "date_of_birth": date(2000, 3, 15),
        "age": 24,
        "city": "Jerusalem",
        "community": Community.LITVISH,
        "education": Education(
            current_institution="Mir Yeshiva",
            current_study=None,
            previous_institutions=[],
        ),
        "family": Family(
            father_profession="Rabbi",
            mother_profession="Teacher",
            siblings=[],
            num_brothers=0,
            num_sisters=0,
        ),
        "character_traits": "Serious learner, kind and thoughtful person.",
        "preferences": "Looking for a serious girl from a good home.",
        "status": CandidateStatus.ACTIVE,
        "notes": None,
        "profile_embedding": [],
        "preferences_embedding": [],
        "profile_text_hash": "",
        "preferences_text_hash": "",
        "embedding_model": "",
        "embedding_updated_at": None,
        "created_by": None,
        "updated_by": None,
    }
    from datetime import datetime
    defaults["created_at"] = datetime.utcnow()
    defaults["updated_at"] = datetime.utcnow()
    defaults.update(overrides)
    return CandidateInDB(**defaults)


def _mock_api_call(vectors: list[list[float]]) -> AsyncMock:
    """Return an AsyncMock that mimics _call_embeddings_api returning vectors."""
    return AsyncMock(return_value=vectors)


# ---------------------------------------------------------------------------
# build_profile_text
# ---------------------------------------------------------------------------

def test_build_profile_text_contains_institution():
    candidate = _make_candidate()
    text = build_profile_text(candidate)
    assert "Mir Yeshiva" in text


def test_build_profile_text_contains_city():
    candidate = _make_candidate()
    text = build_profile_text(candidate)
    assert "Jerusalem" in text


def test_build_profile_text_contains_community():
    candidate = _make_candidate()
    text = build_profile_text(candidate)
    assert "litvish" in text.lower()


def test_build_profile_text_contains_character_traits():
    candidate = _make_candidate()
    text = build_profile_text(candidate)
    assert candidate.character_traits in text


def test_build_preferences_text_contains_preferences():
    candidate = _make_candidate()
    text = build_preferences_text(candidate)
    assert candidate.preferences in text


def test_build_profile_text_not_empty():
    candidate = _make_candidate()
    assert len(build_profile_text(candidate)) > 50


# ---------------------------------------------------------------------------
# embed_candidate — calls API and stores vectors
# ---------------------------------------------------------------------------

async def test_embed_candidate_stores_embeddings(test_db):
    candidate = _make_candidate()

    fake_vector = [0.1] * 3072

    from bson import ObjectId
    await test_db["candidates"].insert_one({
        "_id": candidate.id,
        **candidate.model_dump(exclude={"id"}),
        "gender": candidate.gender.value,
        "status": candidate.status.value,
        "community": candidate.community.value,
        "date_of_birth": str(candidate.date_of_birth),
    })

    with patch("app.services.embeddings._call_embeddings_api", _mock_api_call([fake_vector, fake_vector])):
        await embed_candidate(test_db, candidate)

    doc = await test_db["candidates"].find_one({"_id": candidate.id})
    assert doc is not None
    assert len(doc.get("profile_embedding", [])) == 3072
    assert len(doc.get("preferences_embedding", [])) == 3072
    assert doc["profile_text_hash"] != ""
    assert doc["preferences_text_hash"] != ""


async def test_embed_candidate_skips_when_hash_unchanged(test_db):
    from app.services.embeddings import build_profile_text, build_preferences_text
    import hashlib

    candidate = _make_candidate()
    profile_text = build_profile_text(candidate)
    prefs_text = build_preferences_text(candidate)

    # Pre-set the hashes to match current text — no change → should skip
    candidate = _make_candidate(
        profile_text_hash=hashlib.sha256(profile_text.encode()).hexdigest(),
        preferences_text_hash=hashlib.sha256(prefs_text.encode()).hexdigest(),
        profile_embedding=[0.5] * 3072,
        preferences_embedding=[0.5] * 3072,
    )

    with patch("app.services.embeddings._call_embeddings_api", new=AsyncMock()) as mock_api:
        await embed_candidate(test_db, candidate)
        mock_api.assert_not_called()


async def test_embed_candidate_force_re_embeds(test_db):
    from app.services.embeddings import build_profile_text, build_preferences_text
    import hashlib

    profile_text = build_profile_text(_make_candidate())
    prefs_text = build_preferences_text(_make_candidate())
    candidate = _make_candidate(
        profile_text_hash=hashlib.sha256(profile_text.encode()).hexdigest(),
        preferences_text_hash=hashlib.sha256(prefs_text.encode()).hexdigest(),
        profile_embedding=[0.5] * 3072,
        preferences_embedding=[0.5] * 3072,
    )

    fake_vector = [0.9] * 3072

    from bson import ObjectId
    await test_db["candidates"].insert_one({
        "_id": candidate.id,
        **candidate.model_dump(exclude={"id"}),
        "gender": candidate.gender.value,
        "status": candidate.status.value,
        "community": candidate.community.value,
        "date_of_birth": str(candidate.date_of_birth),
    })

    with patch("app.services.embeddings._call_embeddings_api", new=AsyncMock(return_value=[fake_vector, fake_vector])) as mock_api:
        await embed_candidate(test_db, candidate, force=True)
        mock_api.assert_called_once()


# ---------------------------------------------------------------------------
# embed_candidates_bulk
# ---------------------------------------------------------------------------

async def test_embed_candidates_bulk_skips_already_embedded(test_db):
    from datetime import datetime
    from bson import ObjectId

    # Insert two candidates: one with embeddings, one without
    base = {
        "first_name": "Test", "last_name": "User", "gender": "male",
        "date_of_birth": "2000-01-01", "age": 24,
        "city": "City", "community": "litvish",
        "education": {"current_institution": "Yeshiva", "current_study": None, "previous_institutions": []},
        "family": {"father_profession": "Rabbi", "mother_profession": "Teacher", "siblings": [], "num_brothers": 0, "num_sisters": 0},
        "character_traits": "Good person", "preferences": "Good match",
        "status": "active", "notes": None,
        "preferences_embedding": [], "profile_text_hash": "", "preferences_text_hash": "",
        "embedding_model": "", "embedding_updated_at": None,
        "created_by": None, "updated_by": None,
        "created_at": datetime.utcnow(), "updated_at": datetime.utcnow(),
    }

    embedded = {**base, "_id": ObjectId(), "profile_embedding": [0.1] * 3072}
    not_embedded = {**base, "_id": ObjectId(), "profile_embedding": [], "first_name": "Unembedded"}

    await test_db["candidates"].insert_many([embedded, not_embedded])

    with patch("app.services.embeddings.embed_candidate", new=AsyncMock()) as mock_embed:
        await embed_candidates_bulk(test_db)
        # Only the candidate without embeddings should be processed
        assert mock_embed.call_count == 1
        called_candidate = mock_embed.call_args[0][1]
        assert called_candidate.first_name == "Unembedded"
