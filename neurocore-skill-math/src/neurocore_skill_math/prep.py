"""Group 1 — problem preparation (LLM-backed).

Turn a natural-language problem into a structured statement, classify its domain,
and normalize it for downstream tools.
"""
from __future__ import annotations

from typing import Any

from flowengine import FlowContext
from neurocore import SkillMeta

from neurocore_skill_math._base import STATUS_OK
from neurocore_skill_math._llm import LlmMathSkill

_KNOWN_DOMAINS = [
    "number_theory", "algebra", "analysis", "geometry", "combinatorics",
    "group_theory", "logic", "probability", "linear_algebra", "other",
]


class MathProblemParserSkill(LlmMathSkill):
    default_input_key = "problem"
    default_output_key = "math.parsed"

    skill_meta = SkillMeta(
        name="math_problem_parser",
        version="0.1.0",
        description="Parse a natural-language math problem into assumptions + goal.",
        author="NeuroCore Contributors",
        requires_llm=True,
        consumes=["problem"],
        provides=["math.parsed"],
        tags=["math", "nlp", "parsing", "llm"],
        config_schema={"properties": {
            "input_key": {"type": "string"}, "output_key": {"type": "string"},
        }},
    )

    async def _compute(self, payload: Any, context: FlowContext) -> dict[str, Any]:
        problem = self._text(payload)
        system = (
            "You parse mathematics problems. Return ONLY JSON with keys: "
            '"statement" (string), "assumptions" (string array), "goal" (string), '
            '"variables" (string array).'
        )
        parsed = await self._ask_json(f"Problem:\n{problem}", system)
        parsed.setdefault("statement", problem)
        return self.envelope(STATUS_OK, result=parsed)


class MathDomainClassifierSkill(LlmMathSkill):
    default_input_key = "math.parsed"
    default_output_key = "math.domain"

    skill_meta = SkillMeta(
        name="math_domain_classifier",
        version="0.1.0",
        description="Classify a math problem's domain and suggest backends.",
        author="NeuroCore Contributors",
        requires_llm=True,
        consumes=["math.parsed"],
        provides=["math.domain"],
        tags=["math", "classification", "llm"],
        config_schema={"properties": {
            "input_key": {"type": "string"}, "output_key": {"type": "string"},
        }},
    )

    async def _compute(self, payload: Any, context: FlowContext) -> dict[str, Any]:
        statement = self._text(payload, "statement")
        system = (
            "Classify the mathematical domain. Return ONLY JSON with keys: "
            f'"domain" (one of {_KNOWN_DOMAINS}), '
            '"suggested_backends" (array of: sympy, sage, pari_gp, gap, z3, cvc5, '
            'lean4, isabelle, coq).'
        )
        result = await self._ask_json(f"Statement:\n{statement}", system)
        domain = result.get("domain", "other")
        if domain not in _KNOWN_DOMAINS:
            domain = "other"
        result["domain"] = domain
        # Route to a domain-specific port (used by the full validation worker).
        self.port(context, domain)
        return self.envelope(STATUS_OK, result=result, domain=domain)


class MathStatementNormalizerSkill(LlmMathSkill):
    default_input_key = "math.parsed"
    default_output_key = "math.normalized"

    skill_meta = SkillMeta(
        name="math_statement_normalizer",
        version="0.1.0",
        description="Normalize a parsed statement into a canonical, tool-friendly form.",
        author="NeuroCore Contributors",
        requires_llm=True,
        consumes=["math.parsed", "math.domain"],
        provides=["math.normalized"],
        tags=["math", "normalization", "llm"],
        config_schema={"properties": {
            "input_key": {"type": "string"}, "output_key": {"type": "string"},
            "domain_key": {"type": "string"},
        }},
    )

    async def _compute(self, payload: Any, context: FlowContext) -> dict[str, Any]:
        statement = self._text(payload, "statement")
        domain = context.get(self.config.get("domain_key", "math.domain"))
        system = (
            "Normalize the mathematical statement for automated tools. Return ONLY "
            'JSON with keys: "normalized" (canonical statement), "expression" '
            "(a single SymPy-parseable expression if applicable, else empty string), "
            '"smtlib" (an SMT-LIB v2 encoding of the negated goal if applicable, else "").'
        )
        result = await self._ask_json(
            f"Domain: {domain}\nStatement:\n{statement}", system
        )
        result.setdefault("normalized", statement)
        return self.envelope(STATUS_OK, result=result)
