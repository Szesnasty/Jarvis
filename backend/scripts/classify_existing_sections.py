"""Classify existing section notes in-place (step 28d backfill).

Walks workspace/memory/, finds notes with `parent` set (section notes),
runs the heuristic classifier, and updates frontmatter if:
  - section_type is absent, OR
  - existing confidence < 0.7  (re-classify uncertain results)

Idempotent: notes already classified with confidence ≥ 0.7 are skipped.

Usage:
  python scripts/classify_existing_sections.py
  python scripts/classify_existing_sections.py --workspace ~/MyJarvis
  python scripts/classify_existing_sections.py --force     # re-classify all
  python scripts/classify_existing_sections.py --dry-run   # print changes, no write
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND))


def _find_section_notes(memory_dir: Path) -> list[Path]:
    """Return all .md notes that have a `parent` field in their frontmatter."""
    from utils.markdown import parse_frontmatter

    results = []
    for md in memory_dir.rglob("*.md"):
        try:
            content = md.read_text(encoding="utf-8")
            fm, _ = parse_frontmatter(content)
            if fm.get("parent"):
                results.append(md)
        except Exception:
            continue
    return results


def _should_reclassify(fm: dict, force: bool) -> bool:
    if force:
        return True
    if "section_type" not in fm:
        return True
    conf = fm.get("section_type_confidence", 0.0)
    try:
        return float(conf) < 0.70
    except (TypeError, ValueError):
        return True


def _update_note(path: Path, stype: str, conf: float) -> None:
    from utils.markdown import parse_frontmatter, add_frontmatter

    content = path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(content)
    fm["section_type"] = stype
    fm["section_type_confidence"] = round(conf, 2)
    new_content = add_frontmatter(body, fm)
    path.write_text(new_content, encoding="utf-8")


async def classify_all(memory_dir: Path, *, force: bool, dry_run: bool) -> None:
    from services.document_classifier import classify_section_heuristic
    from utils.markdown import parse_frontmatter

    notes = _find_section_notes(memory_dir)
    print(f"Found {len(notes)} section note(s) under {memory_dir}")

    updated = skipped = unchanged = 0

    for path in notes:
        content = path.read_text(encoding="utf-8")
        fm, body = parse_frontmatter(content)

        if not _should_reclassify(fm, force):
            unchanged += 1
            continue

        title = fm.get("title", path.stem)
        stype, conf, _signals = classify_section_heuristic(title, body)

        if stype == "other":
            # Heuristic uncertain — keep existing value (or set "other" if absent)
            if "section_type" not in fm and not dry_run:
                fm_update = {**fm, "section_type": "other", "section_type_confidence": round(conf, 2)}
                from utils.markdown import add_frontmatter as _af
                path.write_text(_af(body, fm_update), encoding="utf-8")
            skipped += 1
            continue

        if dry_run:
            print(f"  DRY-RUN: {path.relative_to(memory_dir)} → {stype} ({conf:.2f})")
        else:
            _update_note(path, stype, conf)
        updated += 1

    print(
        f"Done: {updated} updated, {skipped} deferred to 'other', "
        f"{unchanged} skipped (already confident).",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill section_type on existing section notes.")
    parser.add_argument("--workspace", default=None, help="Path to Jarvis workspace (default: ~/Jarvis)")
    parser.add_argument("--force", action="store_true", help="Re-classify even already-confident notes")
    parser.add_argument("--dry-run", action="store_true", help="Print changes without writing")
    args = parser.parse_args()

    workspace = Path(args.workspace).expanduser() if args.workspace else Path.home() / "Jarvis"
    memory_dir = workspace / "memory"
    if not memory_dir.exists():
        print(f"Error: memory dir not found: {memory_dir}", file=sys.stderr)
        sys.exit(1)

    asyncio.run(classify_all(memory_dir, force=args.force, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
