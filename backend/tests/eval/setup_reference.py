"""Setup script for the Step 28c reference eval workspace.

Three modes:
  1. Default (no PDFs available): copies the pre-ingested fixture Markdown files
     into a fresh workspace and indexes them — this is always available.
  2. --verify-shas <pdf_dir>: checks that PDF files in <pdf_dir> match the
     SHA-256 values in reference_pdfs.json. Exits 0 if all match, non-zero otherwise.
  3. --update-shas <pdf_dir>: computes SHA-256 for each PDF found and writes
     them back into reference_pdfs.json (use once after downloading documents).

Usage
-----
  # Prepare workspace from fixture Markdown (always works, no PDFs needed):
  python backend/tests/eval/setup_reference.py --workspace /tmp/jarvis-eval

  # Verify PDFs you have downloaded:
  python backend/tests/eval/setup_reference.py --verify-shas ~/Downloads/eval-pdfs

  # Update the manifest with actual SHA values:
  python backend/tests/eval/setup_reference.py --update-shas ~/Downloads/eval-pdfs
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).parent
FIXTURE_WS = HERE / "fixtures" / "reference_workspace"
MANIFEST = HERE / "fixtures" / "reference_pdfs.json"


# ─── SHA utilities ──────────────────────────────────────────────────────────

def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            data = fh.read(chunk)
            if not data:
                break
            h.update(data)
    return h.hexdigest()


def _load_manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


# ─── Workspace setup from fixture Markdowns ─────────────────────────────────

async def setup_workspace(workspace: Path) -> None:
    """Re-create the reference workspace from the checked-in fixture Markdowns."""
    from models.database import init_database
    from services.memory_service import index_note_file

    print(f"Setting up reference workspace at: {workspace}")

    memory = workspace / "memory"
    app = workspace / "app"
    graph_dir = workspace / "graph"

    memory.mkdir(parents=True, exist_ok=True)
    app.mkdir(parents=True, exist_ok=True)
    graph_dir.mkdir(parents=True, exist_ok=True)

    # Copy fixture Markdowns
    fixture_memory = FIXTURE_WS / "memory"
    if not fixture_memory.exists():
        print(
            f"ERROR: Fixture memory directory not found: {fixture_memory}\n"
            "The reference_workspace fixture should be checked into the repository.",
            file=sys.stderr,
        )
        sys.exit(1)

    shutil.copytree(fixture_memory, memory, dirs_exist_ok=True)

    # Build the SQLite index from the copied Markdowns
    db_path = app / "jarvis.db"
    await init_database(db_path)

    md_files = sorted(memory.rglob("*.md"))
    print(f"Indexing {len(md_files)} Markdown files…")
    for md_path in md_files:
        rel = md_path.relative_to(memory).as_posix()
        try:
            await index_note_file(rel, workspace_path=workspace)
        except Exception as exc:
            print(f"  WARNING: failed to index {rel}: {exc}", file=sys.stderr)

    print(f"Done. {len(md_files)} notes indexed.")
    print(f"Workspace ready: {workspace}")


# ─── SHA verify ─────────────────────────────────────────────────────────────

def cmd_verify_shas(pdf_dir: Path) -> None:
    manifest = _load_manifest()
    errors = []
    for doc in manifest["documents"]:
        pdf_path = pdf_dir / doc["filename"]
        if not pdf_path.exists():
            print(f"  SKIP  {doc['filename']} (not found in {pdf_dir})")
            continue
        expected = doc["sha256"]
        if expected.startswith("PLACEHOLDER"):
            print(f"  SKIP  {doc['filename']} (SHA not set in manifest — run --update-shas first)")
            continue
        actual = sha256_file(pdf_path)
        if actual == expected:
            print(f"  OK    {doc['filename']}")
        else:
            print(f"  FAIL  {doc['filename']}")
            print(f"        expected: {expected}")
            print(f"        got:      {actual}")
            errors.append(doc["filename"])
    if errors:
        print(f"\n{len(errors)} SHA mismatch(es). Aborting.", file=sys.stderr)
        sys.exit(1)
    print("\nAll available PDFs verified.")


# ─── SHA update ─────────────────────────────────────────────────────────────

def cmd_update_shas(pdf_dir: Path) -> None:
    manifest = _load_manifest()
    updated = 0
    for doc in manifest["documents"]:
        pdf_path = pdf_dir / doc["filename"]
        if not pdf_path.exists():
            print(f"  SKIP  {doc['filename']} (not found)")
            continue
        sha = sha256_file(pdf_path)
        doc["sha256"] = sha
        print(f"  SET   {doc['filename']} → {sha[:16]}…")
        updated += 1

    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nUpdated {updated} SHA(s) in {MANIFEST}")


# ─── CLI ────────────────────────────────────────────────────────────────────

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path("/tmp/jarvis-eval"),
                        help="Target workspace path (default: /tmp/jarvis-eval)")
    parser.add_argument("--verify-shas", metavar="PDF_DIR", type=Path,
                        help="Verify SHA-256 of PDFs in PDF_DIR against manifest")
    parser.add_argument("--update-shas", metavar="PDF_DIR", type=Path,
                        help="Compute and record SHA-256 for PDFs in PDF_DIR")
    args = parser.parse_args()

    if args.verify_shas:
        cmd_verify_shas(args.verify_shas)
        return

    if args.update_shas:
        cmd_update_shas(args.update_shas)
        return

    # Default: build workspace from fixture Markdowns
    # Must run from backend/ directory so imports resolve
    sys.path.insert(0, str(HERE.parents[1]))  # backend/
    asyncio.run(setup_workspace(args.workspace))


if __name__ == "__main__":
    main()
