"""SMT-based counterexample search with Z3 and cvc5.

The payload provides an SMT-LIB v2 script that encodes the *search for a
counterexample* (typically the negated conjecture plus its constraints):

- solver returns **sat**  → a counterexample exists → port ``counterexample_found``
- solver returns **unsat** → no counterexample        → port ``no_counterexample``
- **unknown** → port ``no_counterexample`` (could not refute), status ``unknown``

Per the design doc, run counterexample search *before* expensive proof search.
"""
from __future__ import annotations

from typing import Any

from flowengine import FlowContext
from neurocore import SkillMeta

from neurocore_skill_math._availability import lib_available, tool_available
from neurocore_skill_math._base import (
    STATUS_ERROR,
    STATUS_OK,
    STATUS_REFUTED,
    STATUS_UNKNOWN,
    MathSkill,
)
from neurocore_skill_math._formats import as_smtlib, parse_smt_result
from neurocore_skill_math._run import run_cli

_SMT_SCHEMA = {"properties": {
    "input_key": {"type": "string"}, "output_key": {"type": "string"},
    "timeout_seconds": {"type": "integer"},
}}


class _SmtSkill(MathSkill):
    default_input_key = "math.normalized"

    def _route(self, context: FlowContext, verdict: str, *, detail: Any = None) -> dict:
        if verdict == "sat":
            self.port(context, "counterexample_found")
            return self.envelope(STATUS_REFUTED, result={"verdict": "sat", "model": detail},
                                 counterexample_found=True)
        if verdict == "unsat":
            self.port(context, "no_counterexample")
            return self.envelope(STATUS_OK, result={"verdict": "unsat"},
                                 counterexample_found=False)
        self.port(context, "no_counterexample")
        return self.envelope(STATUS_UNKNOWN, result={"verdict": "unknown"},
                             counterexample_found=False)


class Z3SmtCheckSkill(_SmtSkill):
    default_output_key = "counterexamples.z3"
    required_lib = "z3"
    tool_name = "z3"

    skill_meta = SkillMeta(
        name="z3_smt_check",
        version="0.1.0",
        description="Search for a counterexample with the Z3 SMT solver (SMT-LIB input).",
        author="NeuroCore Contributors",
        requires=["z3-solver>=4.12"],
        consumes=["math.normalized"],
        provides=["counterexamples.z3"],
        tags=["math", "smt", "counterexample", "z3"],
        config_schema=_SMT_SCHEMA,
    )

    async def _compute(self, payload: Any, context: FlowContext) -> dict[str, Any]:
        import z3

        smt = as_smtlib(payload)
        if not smt:
            return self.envelope(STATUS_ERROR, error="no SMT-LIB input provided")
        solver = z3.Solver()
        solver.set("timeout", int(self.timeout * 1000))
        solver.from_string(smt)
        result = solver.check()
        if result == z3.sat:
            verdict, model = "sat", str(solver.model())
        elif result == z3.unsat:
            verdict, model = "unsat", None
        else:
            verdict, model = "unknown", None
        return self._route(context, verdict, detail=model)


class Cvc5SmtCheckSkill(_SmtSkill):
    default_output_key = "counterexamples.cvc5"
    tool_name = "cvc5"

    skill_meta = SkillMeta(
        name="cvc5_smt_check",
        version="0.1.0",
        description="Search for a counterexample with the cvc5 SMT solver (SMT-LIB input).",
        author="NeuroCore Contributors",
        requires=["cvc5>=1.1"],
        consumes=["math.normalized"],
        provides=["counterexamples.cvc5"],
        tags=["math", "smt", "counterexample", "cvc5"],
        config_schema=_SMT_SCHEMA,
    )

    def is_available(self) -> bool:
        # Usable via either the cvc5 CLI or the python binding.
        return tool_available("cvc5") or lib_available("cvc5")

    async def _compute(self, payload: Any, context: FlowContext) -> dict[str, Any]:
        smt = as_smtlib(payload)
        if not smt:
            return self.envelope(STATUS_ERROR, error="no SMT-LIB input provided")
        if tool_available("cvc5"):
            res = run_cli(["cvc5", "--lang", "smt2", "-"], stdin=smt, timeout=self.timeout)
            if res.timed_out:
                self.port(context, "no_counterexample")
                from neurocore_skill_math._base import STATUS_TIMEOUT
                return self.envelope(STATUS_TIMEOUT, error="cvc5 timed out", log=res.stderr)
            verdict = parse_smt_result(res.stdout)
            return self._route(context, verdict, detail=res.stdout.strip())
        # Fall back to the python binding via its SMT-LIB parser.
        verdict, model = _cvc5_lib_solve(smt)
        return self._route(context, verdict, detail=model)


def _cvc5_lib_solve(smt: str) -> tuple[str, str | None]:
    """Solve an SMT-LIB script with the cvc5 python binding."""
    import cvc5
    from cvc5 import InputParser

    solver = cvc5.Solver()
    solver.setOption("produce-models", "true")
    parser = InputParser(solver)
    parser.setStringInput(cvc5.InputLanguage.SMT_LIB_2_6, smt, "skill")
    sm = parser.getSymbolManager()
    result = None
    while True:
        cmd = parser.nextCommand()
        if cmd.isNull():
            break
        out = cmd.invoke(solver, sm)
        if out and ("sat" in out or "unsat" in out):
            result = out.strip()
    verdict = parse_smt_result(result or "")
    return verdict, None
