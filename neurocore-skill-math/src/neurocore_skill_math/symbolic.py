"""Symbolic algebra skills backed by SymPy.

- ``sympy_simplify`` — simplify an expression.
- ``sympy_solve`` — solve equation(s) for variable(s).
- ``sympy_calculus`` — differentiate / integrate / limit / series.

Each reads an expression from context (a raw string, or a dict with ``expression`` /
``statement`` / ``expr``) and writes a result envelope (default key ``evidence.sympy``).
"""
from __future__ import annotations

from typing import Any

from flowengine import FlowContext
from neurocore import SkillMeta

from neurocore_skill_math._base import STATUS_ERROR, STATUS_OK, MathSkill


def _expr_str(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    if hasattr(payload, "get"):
        for k in ("expression", "expr", "statement", "normalized"):
            v = payload.get(k)
            if isinstance(v, str) and v.strip():
                return v
    return str(payload or "")


class _SympyBase(MathSkill):
    default_input_key = "math.normalized"
    default_output_key = "evidence.sympy"
    required_lib = "sympy"
    tool_name = "sympy"


class SympySimplifySkill(_SympyBase):
    skill_meta = SkillMeta(
        name="sympy_simplify",
        version="0.1.0",
        description="Simplify a symbolic expression with SymPy.",
        author="NeuroCore Contributors",
        requires=["sympy>=1.12"],
        consumes=["math.normalized"],
        provides=["evidence.sympy"],
        tags=["math", "symbolic", "algebra", "sympy"],
        config_schema={"properties": {
            "input_key": {"type": "string"}, "output_key": {"type": "string"},
        }},
    )

    async def _compute(self, payload: Any, context: FlowContext) -> dict[str, Any]:
        import sympy

        raw = _expr_str(payload)
        if not raw:
            return self.envelope(STATUS_ERROR, error="no expression provided")
        expr = sympy.sympify(raw)
        simplified = sympy.simplify(expr)
        return self.envelope(
            STATUS_OK,
            result={
                "input": str(expr),
                "simplified": str(simplified),
                "latex": sympy.latex(simplified),
            },
        )


class SympySolveSkill(_SympyBase):
    skill_meta = SkillMeta(
        name="sympy_solve",
        version="0.1.0",
        description="Solve equation(s) symbolically with SymPy.",
        author="NeuroCore Contributors",
        requires=["sympy>=1.12"],
        consumes=["math.normalized"],
        provides=["evidence.sympy"],
        tags=["math", "symbolic", "algebra", "sympy"],
        config_schema={"properties": {
            "input_key": {"type": "string"}, "output_key": {"type": "string"},
            "variables": {"type": "array", "items": {"type": "string"}},
        }},
    )

    async def _compute(self, payload: Any, context: FlowContext) -> dict[str, Any]:
        import sympy

        raw = _expr_str(payload)
        if not raw:
            return self.envelope(STATUS_ERROR, error="no equation provided")
        # "lhs = rhs" → Eq(lhs, rhs); otherwise treat as expression == 0.
        if "=" in raw and "==" not in raw:
            lhs, _, rhs = raw.partition("=")
            eq = sympy.Eq(sympy.sympify(lhs), sympy.sympify(rhs))
        else:
            eq = sympy.sympify(raw)
        var_names = self.config.get("variables") or []
        symbols = [sympy.Symbol(v) for v in var_names] or sorted(
            eq.free_symbols, key=str
        )
        solutions = sympy.solve(eq, *symbols, dict=True)
        return self.envelope(
            STATUS_OK,
            result={
                "equation": str(eq),
                "variables": [str(s) for s in symbols],
                "solutions": [{str(k): str(v) for k, v in sol.items()} for sol in solutions],
            },
        )


class SympyCalculusSkill(_SympyBase):
    skill_meta = SkillMeta(
        name="sympy_calculus",
        version="0.1.0",
        description="Differentiate, integrate, take limits, or series-expand with SymPy.",
        author="NeuroCore Contributors",
        requires=["sympy>=1.12"],
        consumes=["math.normalized"],
        provides=["evidence.sympy"],
        tags=["math", "symbolic", "calculus", "sympy"],
        config_schema={"properties": {
            "input_key": {"type": "string"}, "output_key": {"type": "string"},
            "operation": {"type": "string",
                          "enum": ["diff", "integrate", "limit", "series"]},
            "variable": {"type": "string"},
            "point": {"type": "string"},
            "order": {"type": "integer"},
        }},
    )

    async def _compute(self, payload: Any, context: FlowContext) -> dict[str, Any]:
        import sympy

        raw = _expr_str(payload)
        if not raw:
            return self.envelope(STATUS_ERROR, error="no expression provided")
        expr = sympy.sympify(raw)
        op = self.config.get("operation", "diff")
        var = sympy.Symbol(self.config.get("variable") or
                           (str(sorted(expr.free_symbols, key=str)[0])
                            if expr.free_symbols else "x"))
        if op == "diff":
            out = sympy.diff(expr, var)
        elif op == "integrate":
            out = sympy.integrate(expr, var)
        elif op == "limit":
            point = sympy.sympify(self.config.get("point", "0"))
            out = sympy.limit(expr, var, point)
        elif op == "series":
            order = int(self.config.get("order", 6))
            out = expr.series(var, 0, order)
        else:
            return self.envelope(STATUS_ERROR, error=f"unknown operation {op!r}")
        return self.envelope(
            STATUS_OK,
            result={"operation": op, "input": str(expr), "variable": str(var),
                    "output": str(out), "latex": sympy.latex(out)},
        )
