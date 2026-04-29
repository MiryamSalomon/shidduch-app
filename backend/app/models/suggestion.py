"""
Suggestion Models
==================
Pydantic schemas for the ``suggestions`` collection — proposed matches between
a male and female candidate.

A suggestion represents a single (boy, girl) pair proposed either by the AI
matching pipeline or manually by a matchmaker. It tracks the full lifecycle
from initial proposal through contact, meeting, and final outcome
(declined or engaged).

Key design decisions:
    - **``pair_key``**: A unique string ``"<male_id>:<female_id>"`` that
      prevents duplicate suggestions for the same pair. This is enforced
      by a unique MongoDB index.
    - **``history`` array**: Every status change appends an entry with
      timestamp, actor, and optional note. This gives matchmakers a full
      audit trail of how a suggestion progressed — who contacted whom,
      when they met, why it was declined, etc.
    - **Bilingual explanations**: The GPT reranker produces match explanations
      in both Hebrew and English, stored separately so the UI can display
      the user's preferred language without re-calling GPT.
"""

from datetime import datetime

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field

from app.models.common import (
    MongoBaseModel,
    PyObjectId,
    SuggestionSource,
    SuggestionStatus,
)


# =============================================================================
# Nested Sub-Models
# =============================================================================

class SuggestionHistoryEntry(BaseModel):
    """
    A single entry in the suggestion's status change history.

    Every time a matchmaker changes a suggestion's status (e.g. from
    "proposed" to "contacted"), a new entry is appended to the ``history``
    array. This creates a complete timeline of the shidduch process.

    Attributes:
        status: The status the suggestion was changed TO.
        at: When the change happened.
        by: ObjectId of the matchmaker who made the change.
        note: Optional free-text note explaining the change
            (e.g. "נפגשו בשבת, רושם חיובי" — "met on Shabbat, positive impression").
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, json_encoders={ObjectId: str})

    status: SuggestionStatus
    at: datetime = Field(default_factory=datetime.utcnow)
    by: PyObjectId
    note: str | None = None


class ModelVersions(BaseModel):
    """
    Records which AI models were used to generate this suggestion.

    Stored so that when models are upgraded (e.g. from text-embedding-3-large
    to a future Hebrew-tuned model), we can identify which suggestions were
    made with which model version and compare quality.

    Attributes:
        embedding: The embedding model name (e.g. "text-embedding-3-large").
        rerank: The chat model used for reranking (e.g. "gpt-4o-mini").
    """

    embedding: str = ""
    rerank: str = ""


# =============================================================================
# API Input Models
# =============================================================================

class SuggestionCreate(BaseModel):
    """
    Schema for manually creating a suggestion.

    Used by ``POST /api/v1/suggestions`` when a matchmaker wants to record
    a match idea they had themselves (not from the AI pipeline).

    Attributes:
        candidate_male_id: ObjectId of the male candidate.
        candidate_female_id: ObjectId of the female candidate.
        note: Optional note explaining why the matchmaker thinks this is
            a good match.
    """

    candidate_male_id: str = Field(
        ...,
        description="ID of the male candidate",
    )
    candidate_female_id: str = Field(
        ...,
        description="ID of the female candidate",
    )
    note: str | None = Field(
        default=None,
        max_length=2000,
        description="Why the matchmaker thinks this pair could work",
    )


class SuggestionUpdateStatus(BaseModel):
    """
    Schema for updating a suggestion's status.

    Used by ``PATCH /api/v1/suggestions/{id}`` to move a suggestion
    through its lifecycle (proposed → contacted → met → engaged/declined).

    Attributes:
        status: The new status to set.
        note: Optional note explaining the status change.
    """

    status: SuggestionStatus
    note: str | None = Field(
        default=None,
        max_length=2000,
        description="Note about this status change",
    )


# =============================================================================
# Database Model
# =============================================================================

class SuggestionInDB(MongoBaseModel):
    """
    Full suggestion document as stored in MongoDB.

    Attributes:
        candidate_male_id: ObjectId of the male candidate.
        candidate_female_id: ObjectId of the female candidate.
        pair_key: Unique string "<male_id>:<female_id>" — enforced by a
            unique index to prevent duplicate suggestions for the same pair.
        source: How this suggestion was created (AI pipeline or manual).
        status: Current lifecycle status.
        ai_score: Cosine similarity score from Atlas Vector Search (0 to 1).
            Null for manual suggestions.
        rerank_score: Score from the GPT reranker (0 to 10).
            Null if reranking was skipped or for manual suggestions.
        rerank_explanation_he: GPT's explanation of why this is a good match,
            in Hebrew.
        rerank_explanation_en: Same explanation in English.
        model_versions: Which AI models were used to generate this suggestion.
        history: Chronological list of status changes with timestamps and notes.
        created_by: ObjectId of the matchmaker who created this suggestion
            (or a system user ID for AI-generated suggestions).
    """

    candidate_male_id: PyObjectId
    candidate_female_id: PyObjectId
    pair_key: str
    source: SuggestionSource = SuggestionSource.MANUAL
    status: SuggestionStatus = SuggestionStatus.PROPOSED
    ai_score: float | None = None
    rerank_score: float | None = None
    rerank_explanation_he: str | None = None
    rerank_explanation_en: str | None = None
    model_versions: ModelVersions = Field(default_factory=ModelVersions)
    history: list[SuggestionHistoryEntry] = Field(default_factory=list)
    created_by: PyObjectId | None = None


# =============================================================================
# API Response Models
# =============================================================================

class SuggestionOut(BaseModel):
    """
    Full suggestion detail returned by the API.

    Includes both candidate IDs, scores, explanations, and the full
    status history. The frontend fetches candidate details separately
    (or the router can populate summaries via aggregation).

    Attributes:
        id: Document ID as a string.
        candidate_male_id: Male candidate's ID.
        candidate_female_id: Female candidate's ID.
        pair_key: Unique pair identifier.
        source: How this was created (AI or manual).
        status: Current status.
        ai_score: Vector similarity score (0-1).
        rerank_score: GPT rerank score (0-10).
        rerank_explanation_he: Hebrew explanation.
        rerank_explanation_en: English explanation.
        model_versions: AI models used.
        history: Full status change history.
        created_by: ID of the creating matchmaker.
        created_at: Creation timestamp.
        updated_at: Last modification timestamp.
    """

    id: str
    candidate_male_id: str
    candidate_female_id: str
    pair_key: str
    source: SuggestionSource
    status: SuggestionStatus
    ai_score: float | None = None
    rerank_score: float | None = None
    rerank_explanation_he: str | None = None
    rerank_explanation_en: str | None = None
    model_versions: ModelVersions = Field(default_factory=ModelVersions)
    history: list[SuggestionHistoryEntry] = Field(default_factory=list)
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime
