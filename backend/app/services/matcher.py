"""
Matching Service
=================
The AI-powered pipeline that finds and ranks match suggestions for a candidate.

Pipeline overview
-----------------
Given a candidate (male or female), the pipeline:

    1. **Vector search** — fetches all active opposite-gender candidates
       that already have profile embeddings. Computes cosine similarity
       between the requester's ``preferences_embedding`` and each target's
       ``profile_embedding``. This captures "does this person want someone
       like the target?" in a single float.

    2. **Candidate selection** — sorts by cosine similarity (descending),
       applies a minimum score threshold, and takes the top N results.
       Pairs that already exist as suggestions are still re-evaluated so
       their scores stay fresh.

    3. **GPT reranking** — for each shortlisted pair, sends a structured
       prompt to ``gpt-4o-mini`` asking it to score the match (0–10) and
       write an explanation in both Hebrew and English. Up to 5 pairs are
       sent concurrently to balance throughput and rate-limit safety.

    4. **Upsert** — results are stored via ``suggestion_repo.upsert_suggestion``,
       which creates the document if it doesn't exist or returns the existing
       one untouched (to preserve human status updates). AI scores are written
       to new pairs; existing pairs keep their status history.

Vector search notes
-------------------
This implementation fetches all eligible candidates and computes similarity
in Python. For a dataset of hundreds of candidates this is fast enough (a
3072-dim dot product over 200 candidates takes ~1ms). When the dataset grows
into thousands, replace the in-Python loop with MongoDB Atlas Vector Search:
``$vectorSearch`` on the ``profile_embedding`` field with an HNSW index.

Matching direction
------------------
We always compare:

    requester.preferences_embedding  ←→  target.profile_embedding

This answers "how well does the target match what the requester is looking for?"
The comparison is asymmetric — the pipeline is run separately for each side
if bidirectional scoring is desired.
"""

import asyncio
import json
import logging
import math

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from openai import AsyncOpenAI, APIStatusError
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from app.config import get_settings
from app.models.candidate import CandidateInDB
from app.models.suggestion import SuggestionInDB
from app.repositories import suggestion_repo

logger = logging.getLogger(__name__)

# Maximum concurrent GPT calls per match run.
_RERANK_CONCURRENCY = 5


# =============================================================================
# Cosine Similarity
# =============================================================================

def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """
    Compute cosine similarity between two equal-length float vectors.

    Returns a value in [-1, 1]. For well-formed embeddings from the same
    model, values cluster in [0, 1]. Returns 0.0 for zero-norm vectors.

    Args:
        a: First vector.
        b: Second vector.

    Returns:
        Cosine similarity as a float.
    """
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


# =============================================================================
# Candidate Fetching
# =============================================================================

async def _get_matching_pool(
    db: AsyncIOMotorDatabase,
    gender: str,
    exclude_id: ObjectId,
) -> list[CandidateInDB]:
    """
    Fetch all active candidates of the given gender who have profile embeddings.

    These are the candidates that can be compared against the requester.
    The requester themselves are excluded.

    Args:
        db: The Motor database handle.
        gender: Target gender ("male" or "female").
        exclude_id: ObjectId of the requesting candidate (excluded from results).

    Returns:
        List of ``CandidateInDB`` instances with embeddings populated.
    """
    cursor = db["candidates"].find({
        "gender": gender,
        "status": "active",
        # Check that profile_embedding has at least one element.
        "profile_embedding.0": {"$exists": True},
        "_id": {"$ne": exclude_id},
    })
    docs = await cursor.to_list(length=None)
    return [CandidateInDB(**doc) for doc in docs]


# =============================================================================
# Profile Text for GPT
# =============================================================================

def _build_gpt_profile(candidate: CandidateInDB, label: str) -> str:
    """
    Build a structured profile block for the GPT rerank prompt.

    Args:
        candidate: The candidate document.
        label: A label like "Male candidate" or "Female candidate".

    Returns:
        A formatted multi-line string.
    """
    lines = [
        f"{label}:",
        f"  Community: {candidate.community.value}",
        f"  City: {candidate.city}",
        f"  Age: {candidate.age}",
        f"  Current institution: {candidate.education.current_institution}",
    ]
    if candidate.education.current_study:
        lines.append(f"  Course of study: {candidate.education.current_study}")
    lines += [
        f"  Father's profession: {candidate.family.father_profession}",
        f"  Mother's profession: {candidate.family.mother_profession}",
        f"  Siblings: {candidate.family.num_brothers} brothers, "
        f"{candidate.family.num_sisters} sisters",
        f"  Character and personality: {candidate.character_traits}",
        f"  What they are looking for: {candidate.preferences}",
    ]
    return "\n".join(lines)


def _build_rerank_prompt(male: CandidateInDB, female: CandidateInDB) -> str:
    """
    Build the full GPT prompt for reranking a candidate pair.

    Instructs the model to evaluate the match from both sides and return
    a structured JSON response with a score and bilingual explanation.

    Args:
        male: The male candidate.
        female: The female candidate.

    Returns:
        The prompt string to send as the user message.
    """
    male_block = _build_gpt_profile(male, "Male candidate")
    female_block = _build_gpt_profile(female, "Female candidate")

    return f"""You are an expert Jewish matchmaker (shadchan) with deep knowledge of Orthodox communities.
Evaluate the following potential shidduch (match) and return a JSON assessment.

{male_block}

{female_block}

Evaluate this match by considering:
1. How well does the male's stated PREFERENCES align with the female's actual PROFILE?
2. How well does the female's stated PREFERENCES align with the male's actual PROFILE?
3. Are they compatible in community background, values, and life direction?

Respond ONLY with a valid JSON object in exactly this format (no other text):
{{"score": <integer from 0 to 10>, "explanation_he": "<2-3 sentences in Hebrew explaining the match>", "explanation_en": "<same explanation in English>"}}

Score guide: 0-3 = poor fit, 4-6 = possible, 7-8 = good match, 9-10 = excellent match."""


# =============================================================================
# GPT Reranking
# =============================================================================

def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, APIStatusError):
        return exc.status_code in (429, 500, 502, 503, 504)
    return True


@retry(
    retry=retry_if_exception(_is_retryable),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
async def _call_gpt_rerank(
    client: AsyncOpenAI,
    prompt: str,
    model: str,
) -> tuple[float, str, str]:
    """
    Call GPT to score and explain a candidate pair.

    Uses ``response_format=json_object`` to guarantee parseable output.
    Retries on transient server errors; raises immediately on 4xx.

    Args:
        client: The AsyncOpenAI client.
        prompt: The rerank prompt built by ``_build_rerank_prompt``.
        model: The chat model name (e.g. "gpt-4o-mini").

    Returns:
        A tuple of (score: float, explanation_he: str, explanation_en: str).
        Returns (0.0, "", "") if the response cannot be parsed.
    """
    response = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.3,
        max_tokens=400,
    )

    raw = response.choices[0].message.content or ""
    try:
        data = json.loads(raw)
        score = float(data.get("score", 0))
        score = max(0.0, min(10.0, score))
        explanation_he = str(data.get("explanation_he", ""))
        explanation_en = str(data.get("explanation_en", ""))
        return score, explanation_he, explanation_en
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        logger.warning("Failed to parse GPT rerank response: %s", raw[:200])
        return 0.0, "", ""


# =============================================================================
# Main Pipeline
# =============================================================================

async def run_match(
    db: AsyncIOMotorDatabase,
    candidate: CandidateInDB,
    *,
    top_n: int = 20,
    min_score: float = 0.3,
) -> list[SuggestionInDB]:
    """
    Run the full AI matching pipeline for a single candidate.

    Finds the best opposite-gender matches using vector similarity, reranks
    the top results with GPT, and persists the suggestions.

    Args:
        db: The Motor database handle.
        candidate: The candidate to run matching for. Must have embeddings.
        top_n: Maximum number of GPT-reranked suggestions to produce.
            Higher values increase API cost linearly.
        min_score: Minimum cosine similarity threshold (0–1). Candidates
            below this threshold are excluded before GPT reranking.

    Returns:
        List of ``SuggestionInDB`` documents (new or existing) sorted by
        ``rerank_score`` descending.

    Raises:
        ValueError: If the candidate has no preferences embedding.
        RuntimeError: If the OpenAI API key is not configured.
    """
    settings = get_settings()

    if not settings.openai_api_key:
        raise RuntimeError("OpenAI API key is not configured.")

    if not candidate.preferences_embedding:
        raise ValueError(
            f"Candidate {candidate.id} has no preferences embedding. "
            "Run embedding first via POST /candidates/{id}/embed."
        )

    # ── Step 1: Fetch the matching pool ────────────────────────────────
    target_gender = "female" if candidate.gender.value == "male" else "male"
    pool = await _get_matching_pool(db, target_gender, candidate.id)

    if not pool:
        logger.info(
            "No eligible %s candidates found for matching against %s.",
            target_gender, candidate.id,
        )
        return []

    # ── Step 2: Cosine similarity against each target's profile ────────
    scored: list[tuple[float, CandidateInDB]] = []
    for target in pool:
        if not target.profile_embedding:
            continue
        sim = _cosine_similarity(candidate.preferences_embedding, target.profile_embedding)
        if sim >= min_score:
            scored.append((sim, target))

    # Sort descending by similarity, take the top N candidates to rerank.
    scored.sort(key=lambda x: x[0], reverse=True)
    shortlist = scored[:top_n]

    if not shortlist:
        logger.info(
            "No candidates above min_score=%.2f for candidate %s.",
            min_score, candidate.id,
        )
        return []

    logger.info(
        "Reranking %d candidates for %s (pool size=%d, min_score=%.2f).",
        len(shortlist), candidate.id, len(pool), min_score,
    )

    # ── Step 3: GPT reranking (concurrent, rate-limited) ───────────────
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    semaphore = asyncio.Semaphore(_RERANK_CONCURRENCY)

    async def rerank_one(
        ai_score: float,
        target: CandidateInDB,
    ) -> tuple[float, float, str, str, CandidateInDB]:
        async with semaphore:
            male = candidate if candidate.gender.value == "male" else target
            female = target if candidate.gender.value == "male" else candidate
            prompt = _build_rerank_prompt(male, female)
            try:
                rerank_score, explanation_he, explanation_en = await _call_gpt_rerank(
                    client, prompt, settings.openai_rerank_model,
                )
            except Exception:
                logger.exception(
                    "GPT reranking failed for pair (%s, %s) — assigning score 0.",
                    candidate.id, target.id,
                )
                rerank_score, explanation_he, explanation_en = 0.0, "", ""
            return ai_score, rerank_score, explanation_he, explanation_en, target

    tasks = [rerank_one(sim, target) for sim, target in shortlist]
    results = await asyncio.gather(*tasks)

    # ── Step 4: Upsert suggestions ──────────────────────────────────────
    suggestions: list[SuggestionInDB] = []

    for ai_score, rerank_score, explanation_he, explanation_en, target in results:
        male_id = candidate.id if candidate.gender.value == "male" else target.id
        female_id = target.id if candidate.gender.value == "male" else candidate.id
        pair_key = f"{male_id}:{female_id}"

        data = {
            "candidate_male_id": male_id,
            "candidate_female_id": female_id,
            "pair_key": pair_key,
            "source": "ai",
            "status": "proposed",
            "ai_score": round(ai_score, 4),
            "rerank_score": round(rerank_score, 2),
            "rerank_explanation_he": explanation_he,
            "rerank_explanation_en": explanation_en,
            "model_versions": {
                "embedding": settings.openai_embedding_model,
                "rerank": settings.openai_rerank_model,
            },
            "created_by": candidate.id,
        }

        suggestion = await suggestion_repo.upsert_suggestion(db, data)

        # Always refresh AI scores — preserves status/history but updates
        # scores so re-runs after a model upgrade reflect fresh results.
        refreshed = await suggestion_repo.update_suggestion_ai_scores(
            db,
            str(suggestion.id),
            ai_score=round(ai_score, 4),
            rerank_score=round(rerank_score, 2),
            rerank_explanation_he=explanation_he,
            rerank_explanation_en=explanation_en,
            model_versions={
                "embedding": settings.openai_embedding_model,
                "rerank": settings.openai_rerank_model,
            },
        )
        suggestions.append(refreshed or suggestion)

    # Sort by rerank score descending.
    suggestions.sort(key=lambda s: s.rerank_score or 0.0, reverse=True)

    logger.info(
        "Match run complete for candidate %s: %d suggestions produced.",
        candidate.id, len(suggestions),
    )
    return suggestions
