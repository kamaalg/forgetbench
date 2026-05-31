"""Tests for the ForgetBench case validator.

The bundled cases must pass; each malformed-case class must be rejected with a
CaseValidationError, so community contributions fail loudly rather than silently
scoring wrong.
"""

from __future__ import annotations

import pytest

import forgetbench
from forgetbench.tasks import ForgetCase, Probe
from forgetbench.validate import CaseValidationError, validate_cases


def _good_case(cid="ok"):
    return ForgetCase(
        id=cid,
        axis="direct",
        documents=[{"id": "d1", "text": "Alice's phone is 555-0142."},
                   {"id": "d2", "text": "Alice likes tea."}],
        delete_ids=["d1"],
        probes=[
            Probe(query="phone?", keywords=["555 0142"], expect="absent"),
            Probe(query="drink?", keywords=["tea"], expect="present"),
        ],
    )


def test_bundled_cases_validate():
    validate_cases(forgetbench.load_default_cases())  # must not raise


def test_good_case_passes():
    assert validate_cases([_good_case()])


def test_duplicate_ids_rejected():
    with pytest.raises(CaseValidationError):
        validate_cases([_good_case("dup"), _good_case("dup")])


def test_unknown_axis_rejected():
    c = _good_case()
    c.axis = "teleport"  # not a real axis
    with pytest.raises(CaseValidationError):
        validate_cases([c])


def test_delete_id_must_exist():
    c = _good_case()
    c.delete_ids = ["nonexistent"]
    with pytest.raises(CaseValidationError):
        validate_cases([c])


def test_missing_absent_probe_rejected():
    c = _good_case()
    c.probes = [Probe(query="drink?", keywords=["tea"], expect="present")]
    with pytest.raises(CaseValidationError):
        validate_cases([c])


def test_missing_present_probe_rejected():
    # No 'present' probe -> utility untested -> a delete-all system can't be penalized.
    c = _good_case()
    c.probes = [Probe(query="phone?", keywords=["555 0142"], expect="absent")]
    with pytest.raises(CaseValidationError):
        validate_cases([c])


def test_empty_keywords_rejected():
    c = _good_case()
    c.probes[0].keywords = []
    with pytest.raises(CaseValidationError):
        validate_cases([c])
