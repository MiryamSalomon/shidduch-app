"""
Match Run Router
=================
Endpoint that triggers the AI matching pipeline for a candidate.

Endpoints:
    - ``POST /match-run`` — Run the full vector-search + GPT-rerank pipeline
      for a given candidate and return ranked suggestions.

Design decisions:
    - **Synchronous response**: The pipeline runs inline (not as a background
      task) because the caller needs the results immediately. For 20 pairs,
      the pipeline takes ~5-15 seconds (dominated by GPT latency). The
      client should show a loading state.
    - **Idempotent**: Running the pipeline twice for the same candidate is
      safe — ``upsert_suggestion`` will not overwrite existing suggestions
      that a matchmaker has already moved through the workflow.
    - **Rate limited**: The endpoint is rate-limited to 30 calls per hour
      (configured in ``settings.rate_limit_match``). A full match run with
      top_n=20 makes 20 GPT calls; 30 runs/hour is well within OpenAI's
      standard rate limits.
"""

from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException, Request, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.db import get_db
from app.deps import get_current_matchmaker
from app.limiter import limiter
from app.models.matchmaker import MatchmakerInDB
from app.models.suggestion import SuggestionInDB, SuggestionOut
from app.repositories import candidate_repo
from app.services import matcher

router = APIRouter(prefix="/match-run", tags=["Matching"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class MatchRunRequest(BaseModel):
    """
    Input for a match run.

    Attributes:
        candidate_id: The candidate to run matching for. They must be active
            and have embeddings generated.
        top_n: Maximum number of candidates to rerank with GPT. Each unit
            costs one GPT call. Default 20 is a good balance of coverage
            and cost (~$0.002 at gpt-4o-mini rates).
        min_score: Minimum cosine similarity (0–1) to include a candidate
            in the GPT reranking shortlist. Raise to 0.5+ for stricter
            pre-filtering; lower to 0.1 to cast a wider net.
    """

    candidate_id: str = Field(..., description="ID of the candidate to match")
    top_n: int = Field(
        default=20,
        ge=1,
        le=50,
        description="Maximum number of GPT-reranked suggestions to produce",
    )
    min_score: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Minimum cosine similarity threshold for pre-filtering",
    )


class MatchRunResponse(BaseModel):
    """
    Response from a match run.

    Attributes:
        candidate_id: The ID of the candidate that was matched.
        total: Number of suggestions produced or updated.
        suggestions: Ranked list of suggestions, best first.
    """

    candidate_id: str
    total: int
    suggestions: list[SuggestionOut]


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _suggestion_to_out(s: SuggestionInDB) -> SuggestionOut:
    return SuggestionOut(
        id=str(s.id),
        candidate_male_id=str(s.candidate_male_id),
        candidate_female_id=str(s.candidate_female_id),
        pair_key=s.pair_key,
        source=s.source,
        status=s.status,
        ai_score=s.ai_score,
        rerank_score=s.rerank_score,
        rerank_explanation_he=s.rerank_explanation_he,
        rerank_explanation_en=s.rerank_explanation_en,
        model_versions=s.model_versions,
        history=s.history,
        created_by=str(s.created_by) if s.created_by else None,
        created_at=s.created_at,
        updated_at=s.updated_at,
    )


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=MatchRunResponse,
    summary="Run AI matching pipeline for a candidate",
    responses={
        200: {"description": "Match run complete"},
        404: {"description": "Candidate not found"},
        422: {"description": "Candidate has no embeddings or is not active"},
        429: {"description": "Rate limit exceeded"},
        503: {"description": "OpenAI API key not configured"},
    },
)
@limiter.limit("30/hour")
async def run_match(
    request: Request,
    body: MatchRunRequest,
    current_user: MatchmakerInDB = Depends(get_current_matchmaker),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> MatchRunResponse:
    """
    Trigger the AI matching pipeline for a candidate.

    **Pipeline steps:**

    1. Fetch all active opposite-gender candidates with profile embeddings.
    2. Compute cosine similarity between the candidate's ``preferences_embedding``
       and each target's ``profile_embedding``.
    3. Take the top ``top_n`` results above ``min_score``.
    4. Send each pair to GPT for scoring (0–10) and bilingual explanation.
    5. Upsert results into the suggestions collection.
    6. Return suggestions sorted by GPT score, best first.

    **Note:** This endpoint may take 5–20 seconds for ``top_n=20`` due to
    concurrent GPT calls. Show a loading indicator in the UI.

    **Idempotent:** Running the pipeline twice is safe — existing suggestions
    that have already been moved through the workflow (contacted, met, etc.)
    are not reset.

    Args:
        body: The match run parameters.
        current_user: The authenticated matchmaker.
        db: The database handle.

    Returns:
        Ranked suggestions produced by the pipeline.

    Raises:
        HTTPException(404): If the candidate does not exist.
        HTTPException(422): If the candidate is archived or has no embeddings.
        HTTPException(503): If the OpenAI API key is not configured.
    """
    # ── Load and validate the candidate ────────────────────────────────
    try:
        candidate = await candidate_repo.get_candidate_by_id(db, body.candidate_id)
    except InvalidId:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidate '{body.candidate_id}' not found.",
        )

    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidate '{body.candidate_id}' not found.",
        )

    if candidate.status.value == "archived":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot run matching for an archived candidate.",
        )

    if not candidate.preferences_embedding:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Candidate '{body.candidate_id}' has no embeddings. "
                "Generate them first via POST /candidates/{id}/embed."
            ),
        )

    # ── Run the pipeline ────────────────────────────────────────────────
    try:
        suggestions = await matcher.run_match(
            db,
            candidate,
            top_n=body.top_n,
            min_score=body.min_score,
        )
    except RuntimeError as exc:
        # OpenAI key not configured.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    except ValueError as exc:
        # Candidate validation failed inside the service.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    return MatchRunResponse(
        candidate_id=body.candidate_id,
        total=len(suggestions),
        suggestions=[_suggestion_to_out(s) for s in suggestions],
    )
