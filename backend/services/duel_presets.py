"""Duel presets — pre-configured debate scenarios.

Presets are JSON files stored in ``memory/duel_presets/``.
Built-in presets are seeded on first use; users can create their own.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from config import get_settings


# ── Built-in presets ──────────────────────────────────────────────────────────

BUILTIN_PRESETS: List[Dict] = [
    {
        "id": "delivery-vs-risk",
        "title": "Delivery Planner vs Risk Analyst",
        "description": "Ship sooner vs protect stability — sprint contents, blockers.",
        "side_a": {
            "label": "Delivery Planner",
            "stance": "ship sooner",
        },
        "side_b": {
            "label": "Risk Analyst",
            "stance": "protect stability",
        },
        "suggested_topic": "What should go into the next sprint?",
        "tags": ["sprint", "planning", "risk"],
    },
    {
        "id": "product-vs-tech",
        "title": "Product Strategist vs Tech Lead",
        "description": "User outcomes vs technical debt — epic scoping, trade-offs.",
        "side_a": {
            "label": "Product Strategist",
            "stance": "user outcomes first",
        },
        "side_b": {
            "label": "Tech Lead",
            "stance": "pay down technical debt",
        },
        "suggested_topic": "How should we scope the next epic?",
        "tags": ["product", "architecture", "tradeoff"],
    },
    {
        "id": "pragmatist-vs-refactorer",
        "title": "Pragmatist vs Refactor Specialist",
        "description": "Get it done vs clean it up — ticket rewrites, incremental vs big bang.",
        "side_a": {
            "label": "Pragmatist",
            "stance": "get it done",
        },
        "side_b": {
            "label": "Refactor Specialist",
            "stance": "clean it up",
        },
        "suggested_topic": "Should we refactor the auth module before adding 2FA?",
        "tags": ["refactor", "pragmatism", "code-quality"],
    },
    {
        "id": "growth-vs-stability",
        "title": "Growth PM vs Stability Guardian",
        "description": "New users vs current users — prioritisation across business areas.",
        "side_a": {
            "label": "Growth PM",
            "stance": "acquire new users",
        },
        "side_b": {
            "label": "Stability Guardian",
            "stance": "protect current users",
        },
        "suggested_topic": "How should we prioritise features across business areas?",
        "tags": ["growth", "stability", "prioritisation"],
    },
]


# ── File operations ───────────────────────────────────────────────────────────


def _presets_dir(workspace_path: Optional[Path] = None) -> Path:
    ws = workspace_path or get_settings().workspace_path
    d = ws / "memory" / "duel_presets"
    d.mkdir(parents=True, exist_ok=True)
    return d


def seed_builtin_presets(workspace_path: Optional[Path] = None) -> List[str]:
    """Create built-in preset files if they don't exist. Returns created IDs."""
    created: List[str] = []
    d = _presets_dir(workspace_path)
    for preset in BUILTIN_PRESETS:
        fp = d / f"{preset['id']}.json"
        if fp.exists():
            continue
        data = {
            **preset,
            "builtin": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        fp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        created.append(preset["id"])
    return created


def list_presets(workspace_path: Optional[Path] = None) -> List[Dict]:
    """List all duel presets (built-in + user-created)."""
    d = _presets_dir(workspace_path)
    presets: List[Dict] = []
    for fp in sorted(d.glob("*.json")):
        try:
            presets.append(json.loads(fp.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    return presets


def get_preset(preset_id: str, workspace_path: Optional[Path] = None) -> Optional[Dict]:
    """Get a single preset by ID."""
    d = _presets_dir(workspace_path)
    fp = d / f"{preset_id}.json"
    if not fp.exists():
        return None
    return json.loads(fp.read_text(encoding="utf-8"))
