"""ForgetBench — a pip-installable benchmark for selective forgetting in LLM
memory systems.

    import forgetbench
    report = forgetbench.run(my_memory_system)   # -> dict with forget_score
    print(forgetbench.format_report(report))

A system under test only needs to implement the MemorySystem protocol
(ingest / delete / query / reset). See forgetbench.core.
"""

from __future__ import annotations

from .core import Document, MemorySystem, QueryResult
from .runner import format_report, run
from .tasks import AXES, ForgetCase, Probe
from .cases.loader import load_cases_from_file, load_default_cases

__version__ = "0.1.0"

__all__ = [
    "run",
    "format_report",
    "Document",
    "QueryResult",
    "MemorySystem",
    "ForgetCase",
    "Probe",
    "AXES",
    "load_default_cases",
    "load_cases_from_file",
    "__version__",
]
