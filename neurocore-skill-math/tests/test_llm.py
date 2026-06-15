"""Tests for LLM-backed skills using neurocore's MockProvider."""
from __future__ import annotations

import json

from flowengine import FlowContext
from neurocore.llm.provider import MockProvider

from neurocore_skill_math import (
    Lean4FormalizeStatementSkill,
    Lean4RepairSkill,
    LlmProofPlannerSkill,
    MathDomainClassifierSkill,
    MathProblemParserSkill,
    MathStatementNormalizerSkill,
    TheoremRetrieverSkill,
)


def _with_llm(skill_cls, config, response):
    skill = skill_cls()
    skill.init(config)
    provider = MockProvider()
    provider.set_response(response)
    skill.llm = provider
    return skill


async def test_problem_parser():
    resp = json.dumps({"statement": "n>1 ⇒ n has a prime factor",
                       "assumptions": ["n ∈ ℕ", "n > 1"],
                       "goal": "n has a prime factor", "variables": ["n"]})
    skill = _with_llm(MathProblemParserSkill, {}, resp)
    ctx = FlowContext(); ctx.set("problem", "Show every n>1 has a prime factor.")
    out = await skill.process(ctx)
    env = out.get("math.parsed")
    assert env.get("status") == "ok"
    assert env.get("result").get("goal") == "n has a prime factor"


async def test_domain_classifier_sets_port():
    resp = json.dumps({"domain": "number_theory", "suggested_backends": ["pari_gp", "z3"]})
    skill = _with_llm(MathDomainClassifierSkill, {}, resp)
    ctx = FlowContext(); ctx.set("math.parsed", {"statement": "primes"})
    out = await skill.process(ctx)
    assert out.get("math.domain").get("domain") == "number_theory"
    assert ctx.get_active_port() == "number_theory"


async def test_domain_classifier_unknown_domain_falls_back():
    resp = json.dumps({"domain": "astrology"})
    skill = _with_llm(MathDomainClassifierSkill, {}, resp)
    ctx = FlowContext(); ctx.set("math.parsed", {"statement": "x"})
    out = await skill.process(ctx)
    assert out.get("math.domain").get("domain") == "other"


async def test_statement_normalizer():
    resp = json.dumps({"normalized": "forall n>1, exists p prime, p | n",
                       "expression": "", "smtlib": "(assert true)"})
    skill = _with_llm(MathStatementNormalizerSkill, {}, resp)
    ctx = FlowContext(); ctx.set("math.parsed", {"statement": "primes"})
    out = await skill.process(ctx)
    assert "forall" in out.get("math.normalized").get("result").get("normalized")


async def test_proof_planner():
    resp = json.dumps({"approach": "strong induction", "steps": ["base", "step"],
                       "recommended_backend": "lean4", "key_lemmas": []})
    skill = _with_llm(LlmProofPlannerSkill, {}, resp)
    ctx = FlowContext(); ctx.set("math.normalized", "statement")
    out = await skill.process(ctx)
    assert out.get("proof.strategy").get("result").get("approach") == "strong induction"


async def test_theorem_retriever():
    resp = json.dumps({"premises": [{"name": "Nat.exists_prime_and_dvd",
                                     "statement": "...", "source": "Mathlib"}]})
    skill = _with_llm(TheoremRetrieverSkill, {"backends": ["lean_mathlib"]}, resp)
    ctx = FlowContext(); ctx.set("proof.strategy", {"approach": "induction"})
    out = await skill.process(ctx)
    premises = out.get("proof.premises").get("result").get("premises")
    assert premises[0].get("source") == "Mathlib"


async def test_lean_formalize_strips_fences():
    resp = "```lean\ntheorem foo : 1 + 1 = 2 := by norm_num\n```"
    skill = _with_llm(Lean4FormalizeStatementSkill, {}, resp)
    ctx = FlowContext(); ctx.set("math.normalized", "1+1=2")
    out = await skill.process(ctx)
    code = out.get("formal.lean_candidate").get("result").get("candidate")
    assert code.startswith("theorem foo")
    assert "```" not in code


async def test_lean_repair_sets_port():
    skill = _with_llm(Lean4RepairSkill, {}, "theorem foo : True := trivial")
    ctx = FlowContext()
    ctx.set("formal.lean_candidate", {"candidate": "theorem foo : True := by sorry"})
    ctx.set("formal.lean_result", {"errors": "unsolved goals"})
    out = await skill.process(ctx)
    assert out.get("formal.lean_candidate").get("result").get("candidate").startswith("theorem foo")
    assert ctx.get_active_port() == "repaired"


async def test_llm_skill_unavailable_without_provider():
    skill = MathProblemParserSkill()
    skill.init({})  # no llm assigned
    ctx = FlowContext(); ctx.set("problem", "x")
    out = await skill.process(ctx)
    assert out.get("math.parsed").get("status") == "tool_unavailable"
    assert ctx.get_active_port() == "tool_unavailable"
