"""Tests for external-CLI skills: subprocess seam mocked, plus availability degradation.

These run without the real provers installed by monkeypatching `tool_available`
(to force the skill "available") and the module's `run_cli` (to return canned output).
Degradation tests use the real `which`, so absent tools yield `tool_unavailable`.
"""
from __future__ import annotations

import pytest
from flowengine import FlowContext

import neurocore_skill_math.atp as atp
import neurocore_skill_math.cas as cas
import neurocore_skill_math.formal as formal
import neurocore_skill_math.smt as smt
from neurocore_skill_math import (
    CoqCheckSkill,
    EproverProveTptpSkill,
    GapGroupTheorySkill,
    Lean4CheckSkill,
    Mace4CountermodelSkill,
    PariGpNumberTheorySkill,
    Prover9ProveSkill,
    VampireProveTptpSkill,
)
from neurocore_skill_math._run import CliResult


def _force_available(monkeypatch, *modules):
    monkeypatch.setattr("neurocore_skill_math._base.tool_available", lambda name: True)
    for m in modules:
        if hasattr(m, "tool_available"):
            monkeypatch.setattr(m, "tool_available", lambda name: True)


def _stub_run(monkeypatch, module, result: CliResult):
    monkeypatch.setattr(module, "run_cli", lambda *a, **k: result)


def _ctx(key, value):
    c = FlowContext(); c.set(key, value); return c


# -- ATP ---------------------------------------------------------------------

async def test_vampire_proof_found(monkeypatch):
    _force_available(monkeypatch, atp)
    _stub_run(monkeypatch, atp, CliResult(0, "% SZS status Theorem for p", ""))
    skill = VampireProveTptpSkill(); skill.init({})
    ctx = await skill.process(_ctx("math.normalized", "fof(a, conjecture, p)."))
    env = ctx.get("proof.vampire")
    assert env.get("status") == "proved" and env.get("result").get("proof_found") is True
    assert ctx.get_active_port() == "proof_found"


async def test_eprover_no_proof(monkeypatch):
    _force_available(monkeypatch, atp)
    _stub_run(monkeypatch, atp, CliResult(0, "# SZS status CounterSatisfiable", ""))
    skill = EproverProveTptpSkill(); skill.init({})
    ctx = await skill.process(_ctx("math.normalized", "fof(a, conjecture, p)."))
    assert ctx.get("proof.eprover").get("result").get("proof_found") is False
    assert ctx.get_active_port() == "no_proof"


async def test_prover9_proved(monkeypatch):
    _force_available(monkeypatch, atp)
    _stub_run(monkeypatch, atp, CliResult(0, "THEOREM PROVED", ""))
    skill = Prover9ProveSkill(); skill.init({})
    ctx = await skill.process(_ctx("math.normalized", "formulas(goals). p. end_of_list."))
    assert ctx.get("proof.prover9").get("status") == "proved"


async def test_mace4_countermodel_found(monkeypatch):
    _force_available(monkeypatch, atp)
    _stub_run(monkeypatch, atp, CliResult(0, "Exiting with 1 model.\nMODEL ...", ""))
    skill = Mace4CountermodelSkill(); skill.init({})
    ctx = await skill.process(_ctx("math.normalized", "formulas(assumptions). p. end_of_list."))
    env = ctx.get("counterexamples.mace4")
    assert env.get("counterexample_found") is True
    assert ctx.get_active_port() == "counterexample_found"


async def test_atp_timeout(monkeypatch):
    _force_available(monkeypatch, atp)
    _stub_run(monkeypatch, atp, CliResult(-1, "", "", timed_out=True))
    skill = VampireProveTptpSkill(); skill.init({})
    ctx = await skill.process(_ctx("math.normalized", "fof(a, conjecture, p)."))
    assert ctx.get("proof.vampire").get("status") == "timeout"


# -- CAS ---------------------------------------------------------------------

async def test_pari_ok(monkeypatch):
    _force_available(monkeypatch, cas)
    _stub_run(monkeypatch, cas, CliResult(0, "[2, 2; 3, 1]", ""))
    skill = PariGpNumberTheorySkill(); skill.init({})
    ctx = await skill.process(_ctx("math.normalized", "factor(12)"))
    assert ctx.get("evidence.pari").get("result").get("output") == "[2, 2; 3, 1]"


async def test_gap_ok(monkeypatch):
    _force_available(monkeypatch, cas)
    _stub_run(monkeypatch, cas, CliResult(0, "6", ""))
    skill = GapGroupTheorySkill(); skill.init({})
    ctx = await skill.process(_ctx("math.normalized", "Order(SymmetricGroup(3));"))
    assert ctx.get("evidence.gap").get("result").get("output") == "6"


# -- SMT cvc5 (CLI seam) -----------------------------------------------------

async def test_cvc5_unsat_no_counterexample(monkeypatch):
    monkeypatch.setattr(smt, "tool_available", lambda name: True)
    _stub_run(monkeypatch, smt, CliResult(0, "unsat", ""))
    skill = smt.Cvc5SmtCheckSkill(); skill.init({})
    ctx = await skill.process(_ctx("math.normalized", "(assert false)"))
    assert ctx.get("counterexamples.cvc5").get("counterexample_found") is False
    assert ctx.get_active_port() == "no_counterexample"


async def test_cvc5_sat_counterexample(monkeypatch):
    monkeypatch.setattr(smt, "tool_available", lambda name: True)
    _stub_run(monkeypatch, smt, CliResult(0, "sat", ""))
    skill = smt.Cvc5SmtCheckSkill(); skill.init({})
    ctx = await skill.process(_ctx("math.normalized", "(declare-const x Int)(assert (> x 0))"))
    assert ctx.get("counterexamples.cvc5").get("counterexample_found") is True


# -- formal checkers ---------------------------------------------------------

async def test_lean4_check_verified(monkeypatch):
    _force_available(monkeypatch, formal)
    _stub_run(monkeypatch, formal, CliResult(0, "", ""))
    skill = Lean4CheckSkill(); skill.init({})
    ctx = await skill.process(_ctx("formal.lean_candidate", "theorem t : True := trivial"))
    env = ctx.get("formal.lean_result")
    assert env.get("status") == "proved" and env.get("result").get("verified") is True
    assert ctx.get_active_port() == "verified"


async def test_lean4_check_repair_needed(monkeypatch):
    _force_available(monkeypatch, formal)
    _stub_run(monkeypatch, formal, CliResult(1, "", "error: unsolved goals"))
    skill = Lean4CheckSkill(); skill.init({})
    ctx = await skill.process(_ctx("formal.lean_candidate", "theorem t : True := by sorry"))
    assert ctx.get("formal.lean_result").get("result").get("verified") is False
    assert ctx.get_active_port() == "repair_needed"


async def test_coq_check_verified(monkeypatch):
    _force_available(monkeypatch, formal)
    _stub_run(monkeypatch, formal, CliResult(0, "", ""))
    skill = CoqCheckSkill(); skill.init({})
    ctx = await skill.process(_ctx("formal.coq_candidate", "Theorem t : True. Proof. exact I. Qed."))
    assert ctx.get("formal.coq_result").get("result").get("verified") is True


# -- availability degradation (real `which`) ---------------------------------

async def test_unavailable_tool_degrades_gracefully():
    # `vampire` is not installed in CI/dev; the skill must not crash the flow.
    skill = VampireProveTptpSkill(); skill.init({})
    if skill.is_available():
        pytest.skip("vampire is installed; degradation path not exercised")
    ctx = await skill.process(_ctx("math.normalized", "fof(a, conjecture, p)."))
    env = ctx.get("proof.vampire")
    assert env.get("status") == "tool_unavailable" and env.get("available") is False
    assert ctx.get_active_port() == "tool_unavailable"
