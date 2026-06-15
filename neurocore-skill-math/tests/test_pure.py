"""Tests for pure-Python skills: SymPy, mpmath, Z3, and the report builder."""
from __future__ import annotations

from flowengine import FlowContext

from neurocore_skill_math import (
    MpmathHighPrecisionCheckSkill,
    ProofReportBuilderSkill,
    SympyCalculusSkill,
    SympySimplifySkill,
    SympySolveSkill,
    Z3SmtCheckSkill,
)


def _ctx(key, value):
    c = FlowContext()
    c.set(key, value)
    return c


# -- SymPy -------------------------------------------------------------------

async def test_sympy_simplify():
    skill = SympySimplifySkill()
    skill.init({})
    ctx = await skill.process(_ctx("math.normalized", "sin(x)**2 + cos(x)**2"))
    env = ctx.get("evidence.sympy")
    assert env.get("status") == "ok"
    assert env.get("result").get("simplified") == "1"


async def test_sympy_solve():
    skill = SympySolveSkill()
    skill.init({"variables": ["x"]})
    ctx = await skill.process(_ctx("math.normalized", "x**2 - 4 = 0"))
    env = ctx.get("evidence.sympy")
    sols = {s.get("x") for s in env.get("result").get("solutions")}
    assert sols == {"-2", "2"}


async def test_sympy_calculus_diff():
    skill = SympyCalculusSkill()
    skill.init({"operation": "diff", "variable": "x"})
    ctx = await skill.process(_ctx("math.normalized", "x**3"))
    assert ctx.get("evidence.sympy").get("result").get("output") == "3*x**2"


async def test_sympy_empty_input_errors():
    skill = SympySimplifySkill()
    skill.init({})
    ctx = await skill.process(_ctx("math.normalized", ""))
    assert ctx.get("evidence.sympy").get("status") == "error"


# -- mpmath ------------------------------------------------------------------

async def test_mpmath_identity_holds():
    skill = MpmathHighPrecisionCheckSkill()
    skill.init({"precision_digits": 60})
    ctx = await skill.process(_ctx("math.normalized", "sin(pi/6) == 1/2"))
    env = ctx.get("evidence.numeric")
    assert env.get("status") == "ok"
    assert env.get("result").get("holds") is True


async def test_mpmath_evaluate():
    skill = MpmathHighPrecisionCheckSkill()
    skill.init({"precision_digits": 40})
    ctx = await skill.process(_ctx("math.normalized", "pi"))
    val = ctx.get("evidence.numeric").get("result").get("value")
    assert val.startswith("3.14159")


# -- Z3 SMT (real solver) ----------------------------------------------------

async def test_z3_counterexample_found():
    skill = Z3SmtCheckSkill()
    skill.init({})
    ctx = await skill.process(_ctx("math.normalized", "(declare-const x Int)\n(assert (> x 5))"))
    env = ctx.get("counterexamples.z3")
    assert env.get("status") == "refuted"
    assert env.get("counterexample_found") is True
    assert ctx.get_active_port() == "counterexample_found"


async def test_z3_no_counterexample():
    skill = Z3SmtCheckSkill()
    skill.init({})
    smt = "(declare-const x Int)\n(assert (and (> x 0) (< x 0)))"
    ctx = await skill.process(_ctx("math.normalized", smt))
    env = ctx.get("counterexamples.z3")
    assert env.get("status") == "ok"
    assert env.get("counterexample_found") is False
    assert ctx.get_active_port() == "no_counterexample"


# -- report builder ----------------------------------------------------------

async def test_report_verified_when_formal_proves():
    ctx = FlowContext()
    ctx.set("math.normalized", "P")
    ctx.set("formal.lean_result", {"status": "proved", "tool": "lean4",
                                   "result": {"verified": True}})
    ctx.set("evidence.sympy", {"status": "ok", "tool": "sympy", "result": {}})
    skill = ProofReportBuilderSkill()
    skill.init({})
    out = await skill.process(ctx)
    assert out.get("validation_status") == "verified"
    assert ctx.get_active_port() == "verified"


async def test_report_refuted_on_counterexample():
    ctx = FlowContext()
    ctx.set("counterexamples.z3", {"status": "refuted", "tool": "z3",
                                   "counterexample_found": True, "result": {}})
    skill = ProofReportBuilderSkill()
    skill.init({})
    out = await skill.process(ctx)
    assert out.get("validation_status") == "refuted"


async def test_report_partial_on_evidence_only():
    ctx = FlowContext()
    ctx.set("evidence.sympy", {"status": "ok", "tool": "sympy", "result": {}})
    skill = ProofReportBuilderSkill()
    skill.init({})
    out = await skill.process(ctx)
    assert out.get("validation_status") == "partially_supported"
