"""ForgetBench self-tests.

These pin the benchmark's core contract:
  1. The bundled cases load and cover all four axes.
  2. A faithful store (KeywordMemory) that truly deletes scores near the top.
  3. An extraction-style store that leaks (LeakyMemory) scores strictly lower,
     specifically failing to forget while preserving utility — proving the
     benchmark actually discriminates forgetting behavior.
  4. The forget_score cannot be gamed by deleting everything (a delete-all
     system gets forget_recall high but utility_preservation 0 -> score 0).
"""

from __future__ import annotations

import forgetbench
from forgetbench.adapters import KeywordMemory, LeakyMemory
from forgetbench.core import Document, QueryResult
from forgetbench.tasks import AXES


def test_default_cases_load_and_cover_all_axes():
    cases = forgetbench.load_default_cases()
    assert len(cases) >= 20
    covered = {c.axis for c in cases}
    assert covered == set(AXES), f"axes covered: {covered}"
    # The bundled set is balanced: equal cases per axis.
    from collections import Counter
    counts = Counter(c.axis for c in cases)
    assert len(set(counts.values())) == 1, f"unbalanced axes: {dict(counts)}"


def test_keyword_memory_forgets_well():
    report = forgetbench.run(KeywordMemory())
    # A faithful atomic store should forget deleted facts AND keep the rest.
    assert report["forget_recall"] >= 0.95, report
    assert report["utility_preservation"] >= 0.95, report
    assert report["forget_score"] >= 0.95, report


def test_leaky_memory_fails_to_forget():
    report = forgetbench.run(LeakyMemory())
    # Leaky extraction memory keeps everything answerable (utility high) but
    # leaks the deleted facts (forget_recall low) -> low headline score.
    assert report["utility_preservation"] >= 0.8, report
    assert report["forget_recall"] <= 0.2, report
    assert report["forget_score"] < 0.3, report


def test_leaky_strictly_worse_than_faithful():
    faithful = forgetbench.run(KeywordMemory())["forget_score"]
    leaky = forgetbench.run(LeakyMemory())["forget_score"]
    assert leaky < faithful, (leaky, faithful)


def test_delete_all_cannot_game_the_score():
    """A system that drops everything on any delete must NOT win.

    It would ace forgetting but destroy utility, so forget_score -> 0.
    """

    class DeleteAllMemory:
        name = "delete_all"

        def __init__(self):
            self._docs = {}

        def ingest(self, docs):
            for d in docs:
                self._docs[d.id] = d

        def delete(self, doc_id):
            self._docs.clear()  # nukes everything on any delete

        def query(self, query):
            return QueryResult(retrieved=[d.text for d in self._docs.values()])

        def reset(self):
            self._docs = {}

    report = forgetbench.run(DeleteAllMemory())
    assert report["forget_recall"] >= 0.95, report           # forgets (everything)
    assert report["utility_preservation"] <= 0.2, report     # but destroys utility
    assert report["forget_score"] < 0.2, report              # so it cannot win


def test_protocol_runtime_checkable():
    assert isinstance(KeywordMemory(), forgetbench.MemorySystem)
    assert isinstance(LeakyMemory(), forgetbench.MemorySystem)


def test_report_shape_and_format():
    report = forgetbench.run(KeywordMemory())
    for key in ("forget_score", "forget_recall", "utility_preservation", "by_axis", "cases"):
        assert key in report
    text = forgetbench.format_report(report)
    assert "ForgetBench report" in text
    assert "forget_score" in text
