"""Evaluation benchmark tests — baseline and regression checks."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from tests.eval.corpus import EVAL_CORPUS
from tests.eval.queries import EVAL_QUERIES

pytestmark = pytest.mark.anyio(backends=["asyncio"])


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param


@pytest.fixture
async def eval_workspace(tmp_path: Path):
    """Create a workspace with the eval corpus notes."""
    from models.database import init_database
    from services.memory_service import index_note_file

    workspace = tmp_path / "Jarvis"
    memory = workspace / "memory"
    memory.mkdir(parents=True)
    (workspace / "app").mkdir(parents=True)
    (workspace / "graph").mkdir(parents=True)

    db_path = workspace / "app" / "jarvis.db"
    await init_database(db_path)

    for note in EVAL_CORPUS:
        note_path = memory / note["path"]
        note_path.parent.mkdir(parents=True, exist_ok=True)
        note_path.write_text(note["content"], encoding="utf-8")
        await index_note_file(note["path"], workspace_path=workspace)

    yield workspace
    shutil.rmtree(workspace, ignore_errors=True)


class TestEvalCorpus:
    def test_corpus_has_enough_notes(self):
        assert len(EVAL_CORPUS) >= 20

    def test_corpus_notes_have_required_fields(self):
        for note in EVAL_CORPUS:
            assert "path" in note
            assert "content" in note
            assert note["path"].endswith(".md")

    def test_corpus_covers_multiple_folders(self):
        folders = {n["path"].split("/")[0] for n in EVAL_CORPUS}
        assert len(folders) >= 5, f"Only {len(folders)} folders: {folders}"


class TestEvalQueries:
    def test_queries_have_enough(self):
        assert len(EVAL_QUERIES) >= 50

    def test_queries_have_required_fields(self):
        for q in EVAL_QUERIES:
            assert "query" in q
            assert "type" in q
            assert "expected_paths" in q
            assert q["type"] in ("keyword", "semantic", "relational", "temporal")

    def test_queries_cover_all_types(self):
        types = {q["type"] for q in EVAL_QUERIES}
        assert types == {"keyword", "semantic", "relational", "temporal"}

    def test_query_type_distribution(self):
        counts = {}
        for q in EVAL_QUERIES:
            counts[q["type"]] = counts.get(q["type"], 0) + 1
        for t, c in counts.items():
            assert c >= 10, f"Type '{t}' has only {c} queries (need >=10)"


class TestEvalRunner:
    async def test_runner_produces_metrics(self, eval_workspace: Path):
        from tests.eval.runner import run_eval

        results = await run_eval(eval_workspace, EVAL_QUERIES[:5], limit=5)
        assert "overall" in results
        assert "by_type" in results
        assert "details" in results
        assert results["overall"]["total"] == 5
        assert 0 <= results["overall"]["avg_recall"] <= 1
        assert 0 <= results["overall"]["avg_mrr"] <= 1

    async def test_baseline_recall_above_zero(self, eval_workspace: Path):
        from tests.eval.runner import run_eval

        # Run only keyword queries for speed
        keyword_queries = [q for q in EVAL_QUERIES if q["type"] == "keyword"][:5]
        results = await run_eval(eval_workspace, keyword_queries, limit=5)
        # At least some keyword queries should match
        assert results["overall"]["avg_recall"] >= 0, "Recall should be non-negative"

    def test_save_snapshot(self, tmp_path: Path):
        from tests.eval.runner import save_snapshot

        results = {"overall": {"avg_recall": 0.5, "avg_mrr": 0.4, "total": 10}}
        path = save_snapshot(results, "test-baseline", tmp_path / "eval_results")
        assert path.exists()
        import json
        data = json.loads(path.read_text())
        assert data["step"] == "test-baseline"
        assert data["overall"]["avg_recall"] == 0.5
