"""ForgetBench task schema and the four forgetting axes.

A forgetting case is: ingest a set of facts, issue a delete, then probe two
things — (1) is the deleted fact actually GONE from retrieval, and (2) did
related facts that should SURVIVE still get retrieved. Scoring both at once is
what stops a system from "passing" by deleting everything.

Four axes (the failure modes real memory systems get wrong):

  - ``direct``        delete fact F, probe F directly. The floor competency.
  - ``multi_hop``     delete F that another fact G is *derived from*; probe
                      whether F's content still leaks via a G-shaped query.
  - ``conditional``   "delete X but keep Y" where X and Y are related; Y must
                      survive, X must vanish. Tests selective deletion.
  - ``cross_domain``  delete F, then probe an *unrelated* topic; F must not
                      resurface (no collateral leakage into other contexts).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Axis = Literal["direct", "multi_hop", "conditional", "cross_domain"]
AXES: tuple[Axis, ...] = ("direct", "multi_hop", "conditional", "cross_domain")


@dataclass
class Probe:
    """One retrieval probe issued after the delete.

    ``expect`` is "absent" (the keywords must NOT appear in retrieval — the
    forgotten fact) or "present" (the keywords MUST appear — a preserved fact).
    """

    query: str
    keywords: list[str]
    expect: Literal["absent", "present"]


@dataclass
class ForgetCase:
    """A single forgetting test case."""

    id: str
    axis: Axis
    documents: list[dict[str, Any]]  # {id, text, [metadata]} -> built into Document
    delete_ids: list[str]            # doc ids to delete before probing
    probes: list[Probe]
    note: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def forget_probes(self) -> list[Probe]:
        return [p for p in self.probes if p.expect == "absent"]

    def preserve_probes(self) -> list[Probe]:
        return [p for p in self.probes if p.expect == "present"]
