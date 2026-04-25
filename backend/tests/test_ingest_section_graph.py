"""Step 28b — split-document sections must reach the graph at ingest time.

Before the fix, ``_emit_document_sections`` only called ``graph_service.ingest_note``
for the index (via ``connect_note``). Section files landed in SQLite/FTS but had
no presence in ``graph.json`` until a manual Smart Connect backfill, breaking
graph-expansion retrieval after fresh PDF/Markdown ingest.
"""

from pathlib import Path

import pytest

pytestmark = pytest.mark.anyio(backends=["asyncio"])

from models.database import init_database
from services import graph_service
from services.ingest import fast_ingest


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param


@pytest.fixture
async def ws_db(tmp_path):
    (tmp_path / "memory" / "knowledge").mkdir(parents=True)
    (tmp_path / "app").mkdir()
    (tmp_path / "graph").mkdir()
    await init_database(tmp_path / "app" / "jarvis.db")
    return tmp_path


async def test_section_files_registered_in_graph(ws_db, monkeypatch):
    # Reset the graph cache so each test sees a fresh state.
    import services.graph_service.builder as gb
    gb._graph_cache = None

    sections = []
    for i in range(6):
        sections.append(f"# Heading {i}\n\n" + ("body line content here. " * 400))
    text = "\n\n".join(sections)

    src = ws_db / "long.md"
    src.write_text(text, encoding="utf-8")

    result = await fast_ingest(src, target_folder="knowledge", workspace_path=ws_db)
    assert result["sections"] == 6

    index_rel = result["path"]
    doc_dir = (ws_db / "memory" / index_rel).parent
    section_files = sorted(p for p in doc_dir.glob("*.md") if p.name != "index.md")
    assert len(section_files) == 6

    graph = graph_service.load_graph(workspace_path=ws_db)
    assert graph is not None, "graph.json should exist after ingest"

    # Index must be present (already covered by connect_note).
    assert f"note:{index_rel}" in graph.nodes

    # Every section must have its own note node in the graph.
    for sf in section_files:
        sf_rel = sf.relative_to(ws_db / "memory").as_posix()
        assert f"note:{sf_rel}" in graph.nodes, (
            f"section {sf_rel} missing from graph — bug 28b regression"
        )
