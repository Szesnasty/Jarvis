"""Quick smoke for new chunking strategy."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from services.chunking import chunk_markdown  # noqa: E402

paths = [
    os.path.expanduser("~/Jarvis/memory/jira/OPS/OPS-13.md"),
    os.path.expanduser("~/Jarvis/memory/jira/OPS/OPS-26.md"),
    os.path.expanduser("~/Jarvis/memory/jira/PROJ/PROJ-38.md"),
]

for p in paths:
    if not os.path.exists(p):
        print(f"skip (missing): {p}")
        continue
    content = open(p).read()
    chunks = chunk_markdown(content, subject_kind="jira_issue")
    print(f"\n=== {os.path.basename(p)}  ->  {len(chunks)} chunks ===")
    for c in chunks:
        preview = c.text[:90].replace("\n", " ")
        print(f"  [{c.index:02}] {c.section_title[:28]:28} tok={c.token_count:3}  {preview!r}")
