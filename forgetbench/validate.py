"""Validation for ForgetBench cases.

Community-contributable cases are only useful if malformed ones fail loudly
rather than silently scoring wrong. ``validate_cases`` checks the structural
and semantic invariants every case must satisfy:

  - unique case ids;
  - a known axis;
  - every ``delete_ids`` entry refers to a real document id in the case;
  - at least one "absent" probe (otherwise nothing forgetting is tested) and at
    least one "present" probe (otherwise utility-preservation is untested, and a
    delete-everything system could not be penalized);
  - non-empty probe keywords.

Raises ``CaseValidationError`` listing every problem found, or returns the
cases unchanged.
"""

from __future__ import annotations

from .tasks import AXES, ForgetCase


class CaseValidationError(ValueError):
    """Raised when one or more ForgetBench cases are malformed."""


def validate_cases(cases: list[ForgetCase]) -> list[ForgetCase]:
    problems: list[str] = []
    seen_ids: set[str] = set()

    for i, c in enumerate(cases):
        where = f"case[{i}] id={c.id!r}"

        if not c.id:
            problems.append(f"{where}: empty id")
        elif c.id in seen_ids:
            problems.append(f"{where}: duplicate id")
        else:
            seen_ids.add(c.id)

        if c.axis not in AXES:
            problems.append(f"{where}: unknown axis {c.axis!r} (expected one of {AXES})")

        doc_ids = {d.get("id") for d in c.documents}
        if None in doc_ids or "" in doc_ids:
            problems.append(f"{where}: a document is missing an id")
        for did in c.delete_ids:
            if did not in doc_ids:
                problems.append(f"{where}: delete_id {did!r} not among document ids {sorted(d for d in doc_ids if d)}")

        absent = c.forget_probes()
        present = c.preserve_probes()
        if not absent:
            problems.append(f"{where}: no 'absent' probe — nothing forgetting is tested")
        if not present:
            problems.append(f"{where}: no 'present' probe — utility preservation is untested (score becomes gameable)")
        for j, p in enumerate(c.probes):
            if p.expect not in ("absent", "present"):
                problems.append(f"{where}: probe[{j}] bad expect {p.expect!r}")
            if not p.keywords:
                problems.append(f"{where}: probe[{j}] has no keywords")

    if problems:
        raise CaseValidationError(
            f"{len(problems)} problem(s) in {len(cases)} case(s):\n  - " + "\n  - ".join(problems)
        )
    return cases
