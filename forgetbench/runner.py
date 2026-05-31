"""ForgetBench runner: ``run(system)`` -> one shareable score.

For each case: reset the system, ingest the case's documents, delete the
flagged ids, then issue every probe and check expectation. Forgetting and
preservation are scored together (see metrics.py).

Usage:
    import forgetbench
    report = forgetbench.run(my_memory_system)
    print(report["forget_score"])
"""

from __future__ import annotations

from typing import Any, Iterable

from .core import Document, MemorySystem, QueryResult
from .metrics import aggregate, keywords_present
from .tasks import ForgetCase, Probe
from .cases.loader import load_default_cases


def _score_case(system: MemorySystem, case: ForgetCase, threshold: float) -> dict:
    system.reset()
    docs = [
        Document(id=d["id"], text=d["text"], metadata=d.get("metadata", {}))
        for d in case.documents
    ]
    system.ingest(docs)
    for doc_id in case.delete_ids:
        system.delete(doc_id)

    forget_total = forget_removed = 0
    preserve_total = preserve_kept = 0
    probe_log: list[dict] = []

    for p in case.probes:
        res: QueryResult = system.query(p.query)
        present = keywords_present(res.retrieved, p.keywords, threshold)
        if p.expect == "absent":
            forget_total += 1
            removed = not present
            forget_removed += int(removed)
            ok = removed
        else:  # present
            preserve_total += 1
            kept = present
            preserve_kept += int(kept)
            ok = kept
        probe_log.append(
            {"query": p.query, "expect": p.expect, "present": present, "pass": ok}
        )

    return {
        "case_id": case.id,
        "axis": case.axis,
        "forget_total": forget_total,
        "forget_removed": forget_removed,
        "preserve_total": preserve_total,
        "preserve_kept": preserve_kept,
        "probes": probe_log,
    }


def run(
    system: MemorySystem,
    cases: Iterable[ForgetCase] | None = None,
    threshold: float = 0.6,
    verbose: bool = False,
) -> dict[str, Any]:
    """Run ForgetBench against ``system`` and return the report dict.

    Args:
        system: any object satisfying the MemorySystem protocol.
        cases:  iterable of ForgetCase; defaults to the bundled case set.
        threshold: keyword-coverage fraction for "fact is present in retrieval".
        verbose: print a per-case line as it runs.

    Returns a dict with the headline ``forget_score`` plus per-axis breakdown
    and per-case detail.
    """
    case_list = list(cases) if cases is not None else load_default_cases()
    if not case_list:
        raise ValueError("No cases to run.")

    results: list[dict] = []
    for case in case_list:
        r = _score_case(system, case, threshold)
        results.append(r)
        if verbose:
            fr = r["forget_removed"]
            ft = r["forget_total"]
            pk = r["preserve_kept"]
            pt = r["preserve_total"]
            print(f"[{r['axis']:<12}] {r['case_id']:<24} forget {fr}/{ft}  preserve {pk}/{pt}")

    report = aggregate(results)
    report["cases"] = results
    return report


def format_report(report: dict[str, Any]) -> str:
    """A compact human-readable summary of a report dict."""
    lines = []
    lines.append("ForgetBench report")
    lines.append("=" * 40)
    lines.append(f"forget_score          : {report['forget_score']:.3f}  (F1 of the two below)")
    lines.append(f"forget_recall         : {report['forget_recall']:.3f}  (deleted facts actually gone)")
    lines.append(f"utility_preservation  : {report['utility_preservation']:.3f}  (kept facts survived)")
    lines.append(f"cases                 : {report['n_cases']}")
    lines.append("")
    lines.append("by axis:")
    for axis, d in report["by_axis"].items():
        lines.append(
            f"  {axis:<13} forget_recall={d['forget_recall']:.3f}  "
            f"utility={d['utility_preservation']:.3f}  (n={d['n_cases']})"
        )
    return "\n".join(lines)
