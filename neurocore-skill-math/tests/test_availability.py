"""Tests for tool-availability detection and the report structure."""
from __future__ import annotations

from neurocore_skill_math._availability import (
    availability_report,
    lib_available,
    tool_available,
)


def test_lib_available_true_and_false():
    assert lib_available("sympy") is True
    assert lib_available("definitely_not_a_real_module_xyz") is False


def test_tool_available_false_for_missing():
    assert tool_available("definitely-not-a-real-binary-xyz") is False


def test_report_structure():
    report = availability_report()
    assert set(report) == {"cli", "lib"}
    assert "z3" in report["lib"] and "lean" in report["cli"]
    # sympy is a hard dependency, so it must be present in any install.
    assert report["lib"]["sympy"] is True
    assert all(isinstance(v, bool) for sec in report.values() for v in sec.values())
