"""High-precision numeric checking with mpmath.

``mpmath_high_precision_check`` evaluates an expression (or compares two sides of an
equation) to many digits — useful for testing a conjectured identity numerically
before attempting a proof.
"""
from __future__ import annotations

from typing import Any

from flowengine import FlowContext
from neurocore import SkillMeta

from neurocore_skill_math._base import STATUS_ERROR, STATUS_OK, MathSkill


class MpmathHighPrecisionCheckSkill(MathSkill):
    default_input_key = "math.normalized"
    default_output_key = "evidence.numeric"
    required_lib = "mpmath"
    tool_name = "mpmath"

    skill_meta = SkillMeta(
        name="mpmath_high_precision_check",
        version="0.1.0",
        description="Evaluate or compare expressions to high precision with mpmath.",
        author="NeuroCore Contributors",
        requires=["mpmath>=1.3"],
        consumes=["math.normalized"],
        provides=["evidence.numeric"],
        tags=["math", "numeric", "high-precision", "mpmath"],
        config_schema={"properties": {
            "input_key": {"type": "string"}, "output_key": {"type": "string"},
            "precision_digits": {"type": "integer"},
            "tolerance": {"type": "string"},
        }},
    )

    def _expr(self, payload: Any) -> str:
        if isinstance(payload, str):
            return payload
        if hasattr(payload, "get"):
            for k in ("expression", "expr", "statement", "normalized"):
                v = payload.get(k)
                if isinstance(v, str) and v.strip():
                    return v
        return str(payload or "")

    async def _compute(self, payload: Any, context: FlowContext) -> dict[str, Any]:
        import mpmath
        import sympy

        raw = self._expr(payload)
        if not raw:
            return self.envelope(STATUS_ERROR, error="no expression provided")
        dps = int(self.config.get("precision_digits", 50))
        mpmath.mp.dps = dps
        tol = mpmath.mpf(self.config.get("tolerance", "1e-30"))

        def evalf(text: str) -> mpmath.mpf:
            # SymPy parses the expression and evaluates it to `dps` digits
            # (using mpmath internally).
            return mpmath.mpf(str(sympy.sympify(text).evalf(dps)))

        # "lhs == rhs" or "lhs = rhs" → compare both sides; else evaluate.
        sep = "==" if "==" in raw else ("=" if "=" in raw else None)
        if sep:
            lhs, _, rhs = raw.partition(sep)
            lval, rval = evalf(lhs), evalf(rhs)
            diff = abs(lval - rval)
            holds = bool(diff < tol)
            return self.envelope(
                STATUS_OK,
                result={
                    "comparison": raw, "lhs": str(lval), "rhs": str(rval),
                    "abs_diff": str(diff), "holds": holds, "precision_digits": dps,
                },
                holds=holds,
            )
        return self.envelope(
            STATUS_OK,
            result={"expression": raw, "value": str(evalf(raw)),
                    "precision_digits": dps},
        )
