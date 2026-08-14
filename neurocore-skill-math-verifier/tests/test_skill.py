"""Tests for MathVerifierSkill."""
from __future__ import annotations

from flowengine import FlowContext
from neurocore_skill_math_verifier import MathVerifierSkill


def test_skill_meta():
    assert MathVerifierSkill.skill_meta.name == "math_verifier"
    assert "math_verification_result" in MathVerifierSkill.skill_meta.provides
