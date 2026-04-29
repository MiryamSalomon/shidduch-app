"""
Embedding Service
==================
Generates and caches OpenAI text embeddings for candidate profiles.

Each candidate has two embedding vectors:
    - **Profile embedding** (3072-dim): represents who the candidate IS.
      Built from their community, education, family background, and
      ``character_traits`` free-text description.
    - **Preferences embedding** (3072-dim): represents who they WANT.
      Built from the ``preferences`` free-text description.

Matching works by comparing the preferences embedding of one candidate
against the profile embedding of opposite-gender candidates — a high
cosine similarity means their preferences align with who the other person is.

Stale detection
---------------
Before calling OpenAI, this service checks whether the text has actually
changed since the last embedding run. The SHA-256 hash of the canonical
profile/preferences text is stored alongside the embeddings. If the hash
hasn't changed, the embedding is already up to date and the API call is skipped.

This means:
    - Editing a candidate's city or family info will trigger re-embedding.
    - Editing private notes or status will NOT trigger re-embedding.

Retry behaviour
---------------
OpenAI API calls are retried up to 3 times with exponential back-off
(2 → 4 → 8 seconds) using ``tenacity``. Transient failures (rate limits,
timeouts) are retried; validation errors (400s) are not.

Usage
-----
Typically called from FastAPI background tasks after a candidate is
created or updated::

    from fastapi import BackgroundTasks
    from app.services import embeddings

    background_tasks.add_task(embeddings.embed_candidate, db, candidate)

Or called directly to force a refresh::

    await embeddings.embed_candidate(db, candidate, force=True)

Or for a one-off bulk backfill (e.g. after a model upgrade)::

    await embeddings.embed_candidates_bulk(db, force=True)
"""

import hashlib
import logging

from motor.motor_asyncio import AsyncIOMotorDatabase
from openai import AsyncOpenAI, APIStatusError
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.config import get_settings
from app.models.candidate import CandidateInDB
from app.repositories import candidate_repo

logger = logging.getLogger(__name__)


# =============================================================================
# Text Builders
# =============================================================================

def build_profile_text(candidate: CandidateInDB) -> str:
    """
    Build the canonical profile text for a candidate.

    This text is what gets embedded to represent who the candidate IS.
    It combines structured metadata (community, city, education, family)
    with the free-text ``character_traits`` description.

    The format is designed to work well with multilingual embedding models
    like text-embedding-3-large, which handles Hebrew and English in the
    same vector space.

    Args:
        candidate: The candidate document.

    Returns:
        A multi-line string suitable for embedding.
    """
    lines = [
        f"קהילה: {candidate.community.value}",
        f"עיר: {candidate.city}",
        f"גיל: {candidate.age}",
        f"מוסד לימודים נוכחי: {candidate.education.current_institution}",
    ]

    if candidate.education.current_study:
        lines.append(f"תחום לימודים: {candidate.education.current_study}")

    if candidate.education.previous_institutions:
        prev = ", ".join(candidate.education.previous_institutions)
        lines.append(f"מוסדות קודמים: {prev}")

    lines.append(f"מקצוע אב: {candidate.family.father_profession}")
    lines.append(f"מקצוע אם: {candidate.family.mother_profession}")

    if candidate.family.num_brothers or candidate.family.num_sisters:
        lines.append(
            f"משפחה: {candidate.family.num_brothers} אחים, "
            f"{candidate.family.num_sisters} אחיות"
        )

    lines.append("")
    lines.append(candidate.character_traits)

    return "\n".join(lines)


def build_preferences_text(candidate: CandidateInDB) -> str:
    """
    Build the canonical preferences text for a candidate.

    This text represents who the candidate WANTS — it is matched against
    the profile embeddings of opposite-gender candidates.

    For now this is just the raw ``preferences`` field. In a future iteration,
    structured preference fields (age range, community filter) could be
    prepended as labels to improve matching precision.

    Args:
        candidate: The candidate document.

    Returns:
        The preferences description text.
    """
    return candidate.preferences


# =============================================================================
# Helpers
# =============================================================================

def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _is_retryable(exc: BaseException) -> bool:
    """Only retry on server errors (5xx) and rate limits (429), not client errors."""
    if isinstance(exc, APIStatusError):
        return exc.status_code in (429, 500, 502, 503, 504)
    return True


@retry(
    retry=retry_if_exception(_is_retryable),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
async def _call_embeddings_api(
    client: AsyncOpenAI,
    texts: list[str],
    model: str,
) -> list[list[float]]:
    """
    Call the OpenAI Embeddings API with retry logic.

    Batches all texts into a single request (cheaper than separate calls).
    Retries on transient server errors; raises immediately on 4xx validation
    errors.

    Args:
        client: The AsyncOpenAI client.
        texts: List of strings to embed.
        model: The embedding model name.

    Returns:
        List of embedding vectors, one per input text, in the same order.
    """
    response = await client.embeddings.create(input=texts, model=model)
    # Sort by index to guarantee order matches input (OpenAI spec allows reordering).
    sorted_data = sorted(response.data, key=lambda item: item.index)
    return [item.embedding for item in sorted_data]


# =============================================================================
# Public API
# =============================================================================

async def embed_candidate(
    db: AsyncIOMotorDatabase,
    candidate: CandidateInDB,
    *,
    force: bool = False,
) -> bool:
    """
    Compute and persist embeddings for a single candidate if they are stale.

    Checks whether the profile or preferences text has changed since the last
    embedding run using SHA-256 hashes. Only the changed texts are re-embedded,
    batched into a single OpenAI API call when both need updating.

    This function is safe to call unconditionally after every candidate write —
    it is a no-op if nothing has changed and the API key is not configured.

    Args:
        db: The Motor database handle (used to persist embeddings).
        candidate: The candidate document to embed.
        force: If True, re-embed even if hashes match (e.g. after a model
            upgrade where we want fresh vectors from a better model).

    Returns:
        True if embeddings were updated (API was called), False if already
        up-to-date or API key is not configured.
    """
    settings = get_settings()

    if not settings.openai_api_key:
        logger.warning("OpenAI API key not configured — skipping embedding.")
        return False

    # ── Build canonical texts and compute hashes ────────────────────────
    profile_text = build_profile_text(candidate)
    preferences_text = build_preferences_text(candidate)

    profile_hash = _sha256(profile_text)
    preferences_hash = _sha256(preferences_text)

    profile_stale = force or (profile_hash != candidate.profile_text_hash)
    preferences_stale = force or (preferences_hash != candidate.preferences_text_hash)

    if not profile_stale and not preferences_stale:
        logger.debug("Embeddings for candidate %s are up to date.", candidate.id)
        return False

    # ── Collect texts that need embedding ───────────────────────────────
    # Batch both into one API call when possible (half the cost + latency).
    texts: list[str] = []
    embed_profile = False
    embed_preferences = False

    if profile_stale:
        texts.append(profile_text)
        embed_profile = True

    if preferences_stale:
        texts.append(preferences_text)
        embed_preferences = True

    # ── Call the API ─────────────────────────────────────────────────────
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    try:
        vectors = await _call_embeddings_api(client, texts, settings.openai_embedding_model)
    except Exception:
        logger.exception(
            "Failed to generate embeddings for candidate %s after retries.",
            candidate.id,
        )
        raise

    # ── Map vectors back to fields ───────────────────────────────────────
    idx = 0
    profile_embedding: list[float] | None = None
    preferences_embedding: list[float] | None = None
    new_profile_hash: str | None = None
    new_preferences_hash: str | None = None

    if embed_profile:
        profile_embedding = vectors[idx]
        new_profile_hash = profile_hash
        idx += 1

    if embed_preferences:
        preferences_embedding = vectors[idx]
        new_preferences_hash = preferences_hash

    # ── Persist ──────────────────────────────────────────────────────────
    await candidate_repo.update_candidate_embeddings(
        db,
        str(candidate.id),
        profile_embedding=profile_embedding,
        preferences_embedding=preferences_embedding,
        profile_text_hash=new_profile_hash,
        preferences_text_hash=new_preferences_hash,
        embedding_model=settings.openai_embedding_model,
    )

    logger.info(
        "Embeddings updated for candidate %s (profile=%s, preferences=%s).",
        candidate.id,
        embed_profile,
        embed_preferences,
    )
    return True


async def embed_candidates_bulk(
    db: AsyncIOMotorDatabase,
    *,
    force: bool = False,
    batch_size: int = 20,
) -> dict:
    """
    Embed all active candidates whose embeddings are stale or missing.

    Processes candidates one at a time (not truly batched across candidates)
    to keep memory usage low and allow partial progress if the run is
    interrupted. Each candidate's two texts are still batched into a single
    API call.

    Typical use cases:
        - Initial backfill when the service is first deployed.
        - Re-embedding after upgrading to a new model version (use ``force=True``).
        - Catching up after a period of downtime.

    Args:
        db: The Motor database handle.
        force: If True, re-embed all candidates regardless of hash state.
        batch_size: Number of candidates to fetch per MongoDB cursor page.
            Does not affect API batching — each candidate is one API call.

    Returns:
        A summary dict with ``updated``, ``skipped``, and ``failed`` counts.
    """
    updated = 0
    skipped = 0
    failed = 0

    skip = 0
    while True:
        query: dict = {"status": {"$ne": "archived"}}
        if not force:
            # Only fetch candidates that have never been embedded.
            # Hash-staleness for already-embedded candidates is handled per-update.
            query["profile_embedding"] = []
        cursor = (
            db["candidates"]
            .find(
                query,
                # Exclude vectors (large) since hash fields are sufficient.
                projection={"profile_embedding": 0, "preferences_embedding": 0},
            )
            .skip(skip)
            .limit(batch_size)
        )
        docs = await cursor.to_list(length=batch_size)

        if not docs:
            break

        for doc in docs:
            candidate = CandidateInDB(**doc)
            try:
                was_updated = await embed_candidate(db, candidate, force=force)
                if was_updated:
                    updated += 1
                else:
                    skipped += 1
            except Exception:
                logger.exception("Failed to embed candidate %s.", candidate.id)
                failed += 1

        skip += batch_size

    logger.info(
        "Bulk embedding complete: updated=%d, skipped=%d, failed=%d.",
        updated,
        skipped,
        failed,
    )
    return {"updated": updated, "skipped": skipped, "failed": failed}
