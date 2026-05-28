#!/usr/bin/env python3
"""Step 29 — migrate legacy ``agents/{id}/*`` files into ``memory/`` and
normalise ``agents/{id}.json`` to the new ``scope`` schema.

For every file under ``agents/{spec_id}/`` the script:

1. Runs it through ``fast_ingest`` with
   ``target_folder=f"knowledge/{spec_id}"`` and
   ``extra_frontmatter={"specialists": [spec_id], "visibility": "private"}``.
2. Moves the original file to ``.trash/agents-migration/{spec_id}/``.
3. Updates ``agents/{spec_id}.json`` so legacy ``sources`` is preserved
   under ``scope.folders`` and ``scope.include_owned`` defaults to True.

Idempotent: re-running skips files that are already gone from ``agents/``.

Usage::

    python scripts/migrate-specialist-files.py [--workspace PATH] [--dry-run]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
from pathlib import Path


def _add_backend_to_path() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root / "backend"))


def _normalise_spec_json(spec_path: Path, dry_run: bool) -> bool:
    try:
        data = json.loads(spec_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[skip] cannot parse {spec_path}: {exc}")
        return False
    scope = data.get("scope") or {}
    if not isinstance(scope, dict):
        scope = {}
    legacy_sources = data.get("sources")
    if isinstance(legacy_sources, list) and not scope.get("folders"):
        scope["folders"] = list(legacy_sources)
    scope.setdefault("folders", [])
    scope.setdefault("tags", [])
    scope.setdefault("include_owned", True)
    if data.get("scope") == scope and "sources" not in data:
        return False
    data["scope"] = scope
    data.pop("sources", None)
    if dry_run:
        print(f"[dry] would normalise {spec_path}")
        return True
    spec_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return True


async def _migrate(workspace: Path, dry_run: bool) -> None:
    _add_backend_to_path()
    from services.ingest import fast_ingest  # type: ignore

    agents_dir = workspace / "agents"
    trash_root = workspace / ".trash" / "agents-migration"
    if not agents_dir.exists():
        print(f"No agents directory at {agents_dir}; nothing to migrate.")
        return

    spec_files = sorted(p for p in agents_dir.glob("*.json") if p.is_file())
    if not spec_files:
        print("No specialist JSON files found.")
        return

    for spec_json in spec_files:
        spec_id = spec_json.stem
        spec_dir = agents_dir / spec_id
        _normalise_spec_json(spec_json, dry_run)
        if not spec_dir.is_dir():
            continue
        files = [p for p in spec_dir.iterdir() if p.is_file()]
        if not files:
            continue
        print(f"[{spec_id}] {len(files)} file(s) to migrate")
        trash_dir = trash_root / spec_id
        if not dry_run:
            trash_dir.mkdir(parents=True, exist_ok=True)
        for fp in files:
            if dry_run:
                print(f"  [dry] would ingest {fp.name}")
                continue
            try:
                result = await fast_ingest(
                    fp,
                    target_folder=f"knowledge/{spec_id}",
                    workspace_path=workspace,
                    original_name=fp.name,
                    extra_frontmatter={
                        "specialists": [spec_id],
                        "visibility": "private",
                    },
                )
                print(f"  [ok] {fp.name} -> {result['path']}")
                shutil.move(str(fp), str(trash_dir / fp.name))
            except Exception as exc:  # pragma: no cover — best-effort logging
                print(f"  [fail] {fp.name}: {exc}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=None,
                        help="Workspace root (defaults to settings).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show actions without modifying anything.")
    args = parser.parse_args()

    if args.workspace is None:
        _add_backend_to_path()
        from config import get_settings  # type: ignore
        workspace = Path(get_settings().workspace_path)
    else:
        workspace = args.workspace.resolve()

    print(f"Workspace: {workspace}")
    asyncio.run(_migrate(workspace, args.dry_run))


if __name__ == "__main__":
    main()
