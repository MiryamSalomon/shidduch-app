"""
Repositories Package
=====================
Re-exports all repository functions for convenient importing.

Usage::

    from app.repositories import candidate_repo, matchmaker_repo, suggestion_repo

    candidate = await candidate_repo.get_candidate_by_id(db, "665f...")
"""
