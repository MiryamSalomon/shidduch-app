"""
Candidate Models
=================
Pydantic schemas for the ``candidates`` collection.
"""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field, computed_field

from app.models.common import (
    CandidateStatus,
    Community,
    Gender,
    MongoBaseModel,
    ParentsMaritalStatus,
    PersonalStatus,
    PhoneType,
    PyObjectId,
)


# =============================================================================
# Small Embedded Sub-Documents
# =============================================================================

class Job(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    employer: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=500)


class ContactPhone(BaseModel):
    number: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=100)
    relation: str | None = Field(default=None, max_length=100)


# =============================================================================
# Nested Sub-Models (Embedded Documents)
# =============================================================================

class Sibling(BaseModel):
    relation: str = Field(..., pattern="^(brother|sister)$")
    age: int | None = Field(default=None, ge=0, le=120)
    institution: str | None = None
    marital_status: str | None = Field(default=None, pattern="^(single|married)$")
    # Extended — shown when married
    spouse_lastname: str | None = None
    support_location: str | None = None
    spouse_study: str | None = None
    spouse_occupation: str | None = None


class Education(BaseModel):
    current_institution: str = Field(..., min_length=1)
    current_study: str | None = None
    previous_institutions: list[str] = Field(default_factory=list)
    # Extended
    is_primary_study: bool | None = None
    study_type: str | None = None
    profession: str | None = None
    jobs: list[Job] = Field(default_factory=list)


class Family(BaseModel):
    # Existing required fields (kept for backward compat)
    father_profession: str = Field(default="")
    mother_profession: str = Field(default="")
    siblings: list[Sibling] = Field(default_factory=list)
    num_brothers: int = Field(default=0, ge=0)
    num_sisters: int = Field(default=0, ge=0)

    # Extended father info
    father_name: str | None = None
    father_is_cohen: bool | None = None
    father_origin: str | None = None
    father_occupation_details: str | None = None
    father_youth_study: str | None = None
    father_phone: str | None = None

    # Extended mother info
    mother_name: str | None = None
    mother_origin: str | None = None
    mother_youth_study: str | None = None
    mother_parents_names: str | None = None
    mother_phone: str | None = None

    # Family meta
    family_style: str | None = None
    parents_marital_status: ParentsMaritalStatus | None = None
    family_openness: str | None = None
    address: str | None = None
    family_notes: str | None = None
    contact_phones: list[ContactPhone] = Field(default_factory=list)


# =============================================================================
# API Input Models
# =============================================================================

class CandidateCreate(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    gender: Gender
    date_of_birth: date
    city: str = Field(..., min_length=1, max_length=100)
    community: Community
    education: Education
    family: Family
    character_traits: str = Field(..., min_length=10, max_length=5000)
    preferences: str = Field(..., min_length=10, max_length=5000)
    status: CandidateStatus = CandidateStatus.ACTIVE
    notes: str | None = Field(default=None, max_length=5000)

    # Extended personal fields
    personal_status: PersonalStatus | None = None
    sub_sector: str | None = Field(default=None, max_length=200)
    halakha_viewpoint: str | None = Field(default=None, max_length=200)
    languages: list[str] = Field(default_factory=list)
    residence: str | None = Field(default=None, max_length=200)
    financial_info: str | None = Field(default=None, max_length=500)
    phone_type: PhoneType | None = None
    openness: str | None = Field(default=None, max_length=300)
    clothing_style: str | None = Field(default=None, max_length=200)
    kova_suit_type: str | None = Field(default=None, max_length=200)
    has_headshot: bool | None = None
    has_license: bool | None = None
    is_cohen: bool | None = None
    height: int | None = Field(default=None, ge=100, le=250)
    hair_color: str | None = Field(default=None, max_length=100)
    hobbies_aspirations: str | None = Field(default=None, max_length=2000)


class CandidateUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    date_of_birth: date | None = None
    city: str | None = Field(default=None, min_length=1, max_length=100)
    community: Community | None = None
    education: Education | None = None
    family: Family | None = None
    character_traits: str | None = Field(default=None, min_length=10, max_length=5000)
    preferences: str | None = Field(default=None, min_length=10, max_length=5000)
    status: CandidateStatus | None = None
    notes: str | None = Field(default=None, max_length=5000)

    # Extended personal fields
    personal_status: PersonalStatus | None = None
    sub_sector: str | None = Field(default=None, max_length=200)
    halakha_viewpoint: str | None = Field(default=None, max_length=200)
    languages: list[str] | None = None
    residence: str | None = Field(default=None, max_length=200)
    financial_info: str | None = Field(default=None, max_length=500)
    phone_type: PhoneType | None = None
    openness: str | None = Field(default=None, max_length=300)
    clothing_style: str | None = Field(default=None, max_length=200)
    kova_suit_type: str | None = Field(default=None, max_length=200)
    has_headshot: bool | None = None
    has_license: bool | None = None
    is_cohen: bool | None = None
    height: int | None = Field(default=None, ge=100, le=250)
    hair_color: str | None = Field(default=None, max_length=100)
    hobbies_aspirations: str | None = Field(default=None, max_length=2000)


# =============================================================================
# Database Model
# =============================================================================

class CandidateInDB(MongoBaseModel):
    first_name: str
    last_name: str
    gender: Gender
    date_of_birth: date
    age: int = 0
    city: str
    community: Community
    education: Education
    family: Family
    character_traits: str
    preferences: str
    status: CandidateStatus = CandidateStatus.ACTIVE
    notes: str | None = None

    # Extended personal fields
    personal_status: PersonalStatus | None = None
    sub_sector: str | None = None
    halakha_viewpoint: str | None = None
    languages: list[str] = Field(default_factory=list)
    residence: str | None = None
    financial_info: str | None = None
    phone_type: PhoneType | None = None
    openness: str | None = None
    clothing_style: str | None = None
    kova_suit_type: str | None = None
    has_headshot: bool | None = None
    has_license: bool | None = None
    is_cohen: bool | None = None
    height: int | None = None
    hair_color: str | None = None
    hobbies_aspirations: str | None = None

    # AI / Embedding fields
    profile_embedding: list[float] = Field(default_factory=list)
    preferences_embedding: list[float] = Field(default_factory=list)
    profile_text_hash: str = ""
    preferences_text_hash: str = ""
    embedding_model: str = ""
    embedding_updated_at: datetime | None = None

    # Audit tracking
    created_by: PyObjectId | None = None
    updated_by: PyObjectId | None = None


# =============================================================================
# API Response Models
# =============================================================================

class CandidateOut(BaseModel):
    id: str
    first_name: str
    last_name: str
    gender: Gender
    date_of_birth: date
    age: int
    city: str
    community: Community
    education: Education
    family: Family
    character_traits: str
    preferences: str
    status: CandidateStatus
    notes: str | None = None
    has_embeddings: bool = False
    embedding_model: str = ""
    created_at: datetime
    updated_at: datetime

    # Extended personal fields
    personal_status: PersonalStatus | None = None
    sub_sector: str | None = None
    halakha_viewpoint: str | None = None
    languages: list[str] = Field(default_factory=list)
    residence: str | None = None
    financial_info: str | None = None
    phone_type: PhoneType | None = None
    openness: str | None = None
    clothing_style: str | None = None
    kova_suit_type: str | None = None
    has_headshot: bool | None = None
    has_license: bool | None = None
    is_cohen: bool | None = None
    height: int | None = None
    hair_color: str | None = None
    hobbies_aspirations: str | None = None


class CandidateSummary(BaseModel):
    id: str
    first_name: str
    last_name: str
    gender: Gender
    age: int
    city: str
    community: Community
    current_institution: str
    status: CandidateStatus
    has_embeddings: bool = False
