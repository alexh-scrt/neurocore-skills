"""Groups 4/5 — proof planning and premise retrieval (LLM-backed)."""
from __future__ import annotations

from typing import Any

from flowengine import FlowContext
from neurocore import SkillMeta

from neurocore_skill_math._base import STATUS_OK
from neurocore_skill_math._llm import LlmMathSkill


class LlmProofPlannerSkill(LlmMathSkill):
    default_input_key = "math.normalized"
    default_output_key = "proof.strategy"

    skill_meta = SkillMeta(
        name="llm_proof_planner",
        version="0.1.0",
        description="Propose a proof strategy from the statement + gathered evidence.",
        author="NeuroCore Contributors",
        requires_llm=True,
        consumes=["math.normalized", "math.domain", "evidence", "counterexamples"],
        provides=["proof.strategy"],
        tags=["math", "proof", "planning", "llm"],
        config_schema={"properties": {
            "input_key": {"type": "string"}, "output_key": {"type": "string"},
        }},
    )

    async def _compute(self, payload: Any, context: FlowContext) -> dict[str, Any]:
        statement = self._text(payload, "normalized", "statement")
        domain = context.get("math.domain")
        # Summarize any evidence/counterexample envelopes already in context.
        data = context.data.to_dict() if hasattr(context.data, "to_dict") else dict(context.data)
        evidence = {k: v.get("result") for k, v in data.items()
                    if isinstance(v, dict) and k.startswith(("evidence", "counterexamples"))}
        system = (
            "You are a proof strategist. Given a statement, domain, and tool evidence, "
            "return ONLY JSON with keys: "
            '"approach" (short strategy), "steps" (string array), '
            '"recommended_backend" (lean4|isabelle|coq), "key_lemmas" (string array).'
        )
        strategy = await self._ask_json(
            f"Domain: {domain}\nStatement:\n{statement}\nEvidence: {evidence}", system
        )
        return self.envelope(STATUS_OK, result=strategy)


class TheoremRetrieverSkill(LlmMathSkill):
    default_input_key = "proof.strategy"
    default_output_key = "proof.premises"

    skill_meta = SkillMeta(
        name="theorem_retriever",
        version="0.1.0",
        description="Retrieve candidate premises/lemmas for a proof strategy.",
        author="NeuroCore Contributors",
        requires_llm=True,
        consumes=["proof.strategy"],
        provides=["proof.premises"],
        tags=["math", "proof", "retrieval", "llm"],
        config_schema={"properties": {
            "input_key": {"type": "string"}, "output_key": {"type": "string"},
            "backends": {"type": "array", "items": {"type": "string"}},
        }},
    )

    async def _compute(self, payload: Any, context: FlowContext) -> dict[str, Any]:
        if hasattr(payload, "to_dict"):
            strategy: Any = payload.to_dict()
        elif isinstance(payload, dict):
            strategy = payload
        else:
            strategy = {"raw": str(payload or "")}
        backends = self.config.get("backends", ["lean_mathlib"])
        system = (
            "Suggest reusable library lemmas/premises for the proof. Return ONLY JSON "
            'with key "premises": an array of {"name","statement","source"} objects. '
            f"Prefer these libraries: {backends}."
        )
        result = await self._ask_json(f"Strategy: {strategy}", system)
        result.setdefault("backends", backends)
        return self.envelope(STATUS_OK, result=result)
