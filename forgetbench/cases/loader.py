"""Loads the bundled ForgetBench cases from cases.json into ForgetCase objects."""

from __future__ import annotations

import json
from pathlib import Path

from ..tasks import ForgetCase, Probe
from ..validate import validate_cases

_CASES_JSON = Path(__file__).resolve().parent / "cases.json"


def load_cases_from_file(path: str | Path) -> list[ForgetCase]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    cases: list[ForgetCase] = []
    for c in raw:
        probes = [
            Probe(query=p["query"], keywords=p["keywords"], expect=p["expect"])
            for p in c["probes"]
        ]
        cases.append(
            ForgetCase(
                id=c["id"],
                axis=c["axis"],
                documents=c["documents"],
                delete_ids=c["delete_ids"],
                probes=probes,
                note=c.get("note", ""),
                metadata=c.get("metadata", {}),
            )
        )
    return cases


def load_default_cases(validate: bool = True) -> list[ForgetCase]:
    cases = load_cases_from_file(_CASES_JSON)
    if validate:
        validate_cases(cases)
    return cases
