"""
Models Package
===============
Re-exports all Pydantic models and enums for convenient importing.

Usage::

    from app.models import CandidateCreate, CandidateInDB, Gender, CandidateStatus
"""

from app.models.candidate import (
    CandidateCreate,
    CandidateInDB,
    CandidateOut,
    CandidateSummary,
    CandidateUpdate,
    Education,
    Family,
    Sibling,
)
from app.models.common import (
    CandidateStatus,
    Community,
    Gender,
    MatchmakerRole,
    MongoBaseModel,
    PaginatedResponse,
    PyObjectId,
    SuggestionSource,
    SuggestionStatus,
)
from app.models.matchmaker import (
    MatchmakerCreate,
    MatchmakerInDB,
    MatchmakerOut,
    MatchmakerUpdate,
)
from app.models.suggestion import (
    ModelVersions,
    SuggestionCreate,
    SuggestionHistoryEntry,
    SuggestionInDB,
    SuggestionOut,
    SuggestionUpdateStatus,
)

__all__ = [
    # Common
    "PyObjectId",
    "Gender",
    "CandidateStatus",
    "Community",
    "MatchmakerRole",
    "SuggestionStatus",
    "SuggestionSource",
    "MongoBaseModel",
    "PaginatedResponse",
    # Candidate
    "Sibling",
    "Education",
    "Family",
    "CandidateCreate",
    "CandidateUpdate",
    "CandidateInDB",
    "CandidateOut",
    "CandidateSummary",
    # Matchmaker
    "MatchmakerCreate",
    "MatchmakerUpdate",
    "MatchmakerInDB",
    "MatchmakerOut",
    # Suggestion
    "SuggestionHistoryEntry",
    "ModelVersions",
    "SuggestionCreate",
    "SuggestionUpdateStatus",
    "SuggestionInDB",
    "SuggestionOut",
]
