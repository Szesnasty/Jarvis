"""Compatibility facade for enrichment service.

Step 22c implementation lives in the split package:
- services.enrichment.models
- services.enrichment.runtime
- services.enrichment.subjects
- services.enrichment.repository
- services.enrichment.worker
"""

from services.enrichment import (
    SUBJECT_JIRA,
    SUBJECT_NOTE,
    enqueue_item,
    enqueue_jira_issue,
    get_latest_enrichment,
    queue_status,
    rerun,
    sharpen_all,
    start_workers,
    stop_workers,
)

__all__ = [
    "SUBJECT_JIRA",
    "SUBJECT_NOTE",
    "enqueue_item",
    "enqueue_jira_issue",
    "queue_status",
    "get_latest_enrichment",
    "rerun",
    "sharpen_all",
    "start_workers",
    "stop_workers",
]
