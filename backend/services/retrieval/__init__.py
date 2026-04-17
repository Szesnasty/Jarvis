"""Jira-aware hybrid retrieval package (step 22f).

Re-exports the public ``retrieve()`` function so existing imports
(``from services.retrieval import retrieve``) keep working.
"""

from services.retrieval.pipeline import retrieve, retrieve_with_intent  # noqa: F401
