"""Proof reporting (Group 6).

``proof_report_builder`` gathers every math result envelope written to context and
emits an overall ``validation_status`` plus a ``final_answer`` and ``proof_artifacts``.

Validation rule (per the design doc): formal verification is the only "verified"
status; CAS/SMT/ATP outcomes are evidence unless an independent proof object is
checked. Counterexamples refute.
"""
from __future__ import annotations

from flowengine import FlowContext
from neurocore import SkillMeta

from neurocore_skill_math._base import MathSkill


class ProofReportBuilderSkill(MathSkill):
    default_input_key = "math.normalized"
    default_output_key = "proof_artifacts"
    tool_name = "report"

    skill_meta = SkillMeta(
        name="proof_report_builder",
        version="0.1.0",
        description="Aggregate evidence/counterexamples/proofs into a final proof report.",
        author="NeuroCore Contributors",
        consumes=["evidence", "counterexamples", "proof", "formal"],
        provides=["validation_status", "final_answer", "proof_artifacts"],
        tags=["math", "proof", "report"],
        config_schema={"properties": {
            "status_key": {"type": "string"},
            "answer_key": {"type": "string"},
            "artifacts_key": {"type": "string"},
        }},
    )

    def is_available(self) -> bool:
        return True

    async def process(self, context: FlowContext) -> FlowContext:  # type: ignore[override]
        data = context.data.to_dict() if hasattr(context.data, "to_dict") else dict(context.data)
        envelopes = {
            k: v for k, v in data.items()
            if isinstance(v, dict) and "status" in v and "tool" in v
        }

        def any_match(prefix: str, pred) -> bool:
            return any(pred(v) for k, v in envelopes.items() if k.startswith(prefix))

        verified = any_match("formal", lambda v: v.get("status") in ("proved", "verified")
                             or (v.get("result") or {}).get("verified") is True)
        refuted = any_match("counterexamples", lambda v: v.get("counterexample_found") is True
                            or v.get("status") == "refuted")
        proof_found = any_match("proof", lambda v: v.get("status") == "proved"
                                or (v.get("result") or {}).get("proof_found") is True)
        had_evidence = any(k.startswith("evidence") for k in envelopes)

        if verified:
            status = "verified"
        elif refuted:
            status = "refuted"
        elif proof_found or had_evidence:
            status = "partially_supported"
        elif envelopes:
            status = "unknown"
        else:
            status = "failed"

        tools_run = sorted({str(v.get("tool")) for v in envelopes.values() if v.get("tool")})
        unavailable = sorted(k for k, v in envelopes.items()
                             if v.get("status") == "tool_unavailable")
        statement = context.get("math.normalized") or context.get(self.in_key)
        final_answer = (
            f"validation_status={status}; "
            f"tools_run={tools_run}; "
            + (f"unavailable={unavailable}" if unavailable else "all requested tools ran")
        )
        artifacts = {
            "statement": statement,
            "domain": context.get("math.domain"),
            "envelopes": envelopes,
            "tools_run": tools_run,
            "tools_unavailable": unavailable,
        }

        context.set(self.config.get("status_key", "validation_status"), status)
        context.set(self.config.get("answer_key", "final_answer"), final_answer)
        context.set(self.config.get("artifacts_key", "proof_artifacts"), artifacts)
        self.port(context, status)
        return context
