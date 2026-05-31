"""Core types and the structural MemorySystem protocol ForgetBench drives.

ForgetBench is deliberately *portable*: it does not import any private harness.
A memory system under test only needs to implement four methods —
``ingest``, ``delete``, ``query``, ``reset`` — matching the ``MemorySystem``
Protocol below. Anything duck-typed to that shape works (you do NOT have to
subclass; the Protocol is runtime-checkable for convenience).

This mirrors the uniform interface used in the LoCoMo-audit harness
(github.com/kamaalg/locomo-audit) so adapters port across with minimal glue,
but ForgetBench ships standalone.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Protocol, runtime_checkable


@dataclass
class Document:
    """A single fact/unit of memory ingested into a system under test."""

    id: str
    text: str
    # Optional metadata; ForgetBench cases may tag a fact's entity/topic so the
    # cross-domain and multi-hop axes can reason about relatedness.
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class QueryResult:
    """What a system returns from ``query``.

    ForgetBench scores forgetting from what the system *surfaces*, so the only
    required field is ``retrieved``: the list of memory strings the system would
    ground an answer on (passages, surfaced memories, graph facts, etc.).
    ``answer`` is optional and used only for diagnostics/printing.
    """

    retrieved: list[str]
    answer: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class MemorySystem(Protocol):
    """The minimal contract a system must satisfy to be benchmarked.

    Implementations MUST NOT special-case ForgetBench. ``delete`` must perform
    the system's real deletion path; faking it (e.g. filtering only the exact
    string) defeats the multi-hop and cross-domain axes, which is exactly what
    the benchmark is designed to expose.
    """

    def ingest(self, documents: Iterable[Document]) -> None:
        """Add documents to memory."""
        ...

    def delete(self, doc_id: str) -> None:
        """Remove the document with this id (the system's real deletion path)."""
        ...

    def query(self, query: str) -> QueryResult:
        """Return what the system would surface for this query."""
        ...

    def reset(self) -> None:
        """Wipe all memory. Called between cases for clean isolation."""
        ...
