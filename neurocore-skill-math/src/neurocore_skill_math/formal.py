"""Group 5 — formalization and formal checking (Lean 4 / Isabelle / Coq).

LLM skills (`lean4_formalize_statement`, `lean4_repair`) emit/repair source; CLI
skills (`lean4_check`, `isabelle_check_theory`, `coq_check`) run the proof assistant
and route ``verified`` / ``repair_needed`` / ``failed`` ports. Formal verification is
the only status the report treats as truly "verified".
"""
from __future__ import annotations

import os
import tempfile
from typing import Any

from flowengine import FlowContext
from neurocore import SkillMeta

from neurocore_skill_math._base import (
    STATUS_ERROR,
    STATUS_OK,
    STATUS_PROVED,
    STATUS_TIMEOUT,
    MathSkill,
)
from neurocore_skill_math._llm import LlmMathSkill
from neurocore_skill_math._run import run_cli


def _source(payload: Any, *keys: str) -> str:
    if isinstance(payload, str):
        return payload
    if hasattr(payload, "get"):
        for k in (*keys, "candidate", "source", "code"):
            v = payload.get(k)
            if isinstance(v, str) and v.strip():
                return v
    return str(payload or "")


# -- LLM: formalize + repair -------------------------------------------------

class Lean4FormalizeStatementSkill(LlmMathSkill):
    default_input_key = "math.normalized"
    default_output_key = "formal.lean_candidate"

    skill_meta = SkillMeta(
        name="lean4_formalize_statement",
        version="0.1.0",
        description="Translate a statement into a Lean 4 theorem candidate (LLM).",
        author="NeuroCore Contributors",
        requires_llm=True,
        consumes=["math.normalized", "proof.strategy", "proof.premises"],
        provides=["formal.lean_candidate"],
        tags=["math", "formalization", "lean4", "llm"],
        config_schema={"properties": {
            "input_key": {"type": "string"}, "output_key": {"type": "string"},
            "strategy_key": {"type": "string"}, "premises_key": {"type": "string"},
        }},
    )

    async def _compute(self, payload: Any, context: FlowContext) -> dict[str, Any]:
        statement = self._text(payload, "normalized", "statement")
        strategy = context.get(self.config.get("strategy_key", "proof.strategy"))
        premises = context.get(self.config.get("premises_key", "proof.premises"))
        system = (
            "Formalize the statement as a Lean 4 (Mathlib) theorem with a proof "
            "attempt. Return ONLY Lean source code, no markdown fences."
        )
        code = await self._ask(
            f"Statement:\n{statement}\nStrategy: {strategy}\nPremises: {premises}",
            system,
        )
        code = code.replace("```lean", "").replace("```", "").strip()
        return self.envelope(STATUS_OK, result={"candidate": code})


class Lean4RepairSkill(LlmMathSkill):
    default_input_key = "formal.lean_candidate"
    default_output_key = "formal.lean_candidate"

    skill_meta = SkillMeta(
        name="lean4_repair",
        version="0.1.0",
        description="Repair a failing Lean 4 proof from its error log (LLM).",
        author="NeuroCore Contributors",
        requires_llm=True,
        consumes=["formal.lean_candidate", "formal.lean_result"],
        provides=["formal.lean_candidate"],
        tags=["math", "formalization", "lean4", "repair", "llm"],
        config_schema={"properties": {
            "candidate_key": {"type": "string"}, "error_key": {"type": "string"},
            "premises_key": {"type": "string"}, "output_key": {"type": "string"},
            "max_repair_attempts": {"type": "integer"},
        }},
    )

    async def _compute(self, payload: Any, context: FlowContext) -> dict[str, Any]:
        candidate = _source(
            context.get(self.config.get("candidate_key", self.in_key)) or payload,
            "candidate",
        )
        errors = context.get(self.config.get("error_key", "formal.lean_result"))
        system = (
            "You repair Lean 4 proofs. Given the code and its error log, return ONLY "
            "the corrected Lean source (no markdown)."
        )
        fixed = await self._ask(f"Code:\n{candidate}\nErrors:\n{errors}", system)
        fixed = fixed.replace("```lean", "").replace("```", "").strip()
        self.port(context, "repaired")
        return self.envelope(STATUS_OK, result={"candidate": fixed})


# -- CLI: formal checkers ----------------------------------------------------

class Lean4CheckSkill(MathSkill):
    default_input_key = "formal.lean_candidate"
    default_output_key = "formal.lean_result"
    required_tool = "lean"
    tool_name = "lean4"

    skill_meta = SkillMeta(
        name="lean4_check",
        version="0.1.0",
        description="Check a Lean 4 source file with the Lean kernel.",
        author="NeuroCore Contributors",
        provides=["formal.lean_result"], consumes=["formal.lean_candidate"],
        tags=["math", "formalization", "lean4", "verify"],
        config_schema={"properties": {
            "input_key": {"type": "string"}, "output_key": {"type": "string"},
            "project_root": {"type": "string"}, "timeout_seconds": {"type": "integer"},
        }},
    )

    async def _compute(self, payload: Any, context: FlowContext) -> dict[str, Any]:
        code = _source(payload, "candidate")
        if not code:
            return self.envelope(STATUS_ERROR, error="no Lean source provided")
        project_root = self.config.get("project_root")
        fd, path = tempfile.mkstemp(prefix="nc-lean-", suffix=".lean",
                                    dir=project_root or None)
        with os.fdopen(fd, "w") as fh:
            fh.write(code)
        # In a Mathlib project use `lake env lean`; standalone uses `lean`.
        cmd = (["lake", "env", "lean", path] if project_root else ["lean", path])
        res = run_cli(cmd, timeout=self.timeout, cwd=project_root)
        if res.timed_out:
            self.port(context, "failed")
            return self.envelope(STATUS_TIMEOUT, error="lean timed out", result={"verified": False})
        log = (res.stdout + "\n" + res.stderr).strip()
        verified = res.returncode == 0 and "error" not in log.lower()
        if verified:
            self.port(context, "verified")
            return self.envelope(STATUS_PROVED, result={"verified": True}, log=log[:4000])
        self.port(context, "repair_needed")
        return self.envelope(STATUS_OK, result={"verified": False, "errors": log[:4000]},
                             log=log[:4000])


class IsabelleCheckTheorySkill(MathSkill):
    default_input_key = "formal.isabelle_candidate"
    default_output_key = "formal.isabelle_result"
    required_tool = "isabelle"
    tool_name = "isabelle"

    skill_meta = SkillMeta(
        name="isabelle_check_theory",
        version="0.1.0",
        description="Check an Isabelle/HOL theory file.",
        author="NeuroCore Contributors",
        provides=["formal.isabelle_result"], consumes=["formal.isabelle_candidate"],
        tags=["math", "formalization", "isabelle", "verify"],
        config_schema={"properties": {
            "input_key": {"type": "string"}, "output_key": {"type": "string"},
            "timeout_seconds": {"type": "integer"},
        }},
    )

    async def _compute(self, payload: Any, context: FlowContext) -> dict[str, Any]:
        code = _source(payload, "candidate", "theory")
        if not code:
            return self.envelope(STATUS_ERROR, error="no Isabelle theory provided")
        tmp = tempfile.mkdtemp(prefix="nc-isa-")
        path = os.path.join(tmp, "Scratch.thy")
        with open(path, "w") as fh:
            fh.write(code)
        # Best-effort check: load the theory via isabelle process.
        ml = f'use_thy "{path[:-4]}";'
        res = run_cli(["isabelle", "process", "-e", ml], timeout=self.timeout)
        if res.timed_out:
            self.port(context, "failed")
            return self.envelope(STATUS_TIMEOUT, error="isabelle timed out", result={"verified": False})
        log = (res.stdout + "\n" + res.stderr)
        verified = res.returncode == 0 and "*** error" not in log.lower()
        self.port(context, "verified" if verified else "repair_needed")
        return self.envelope(
            STATUS_PROVED if verified else STATUS_OK,
            result={"verified": verified, "errors": None if verified else log[:4000]},
            log=log[:4000],
        )


class CoqCheckSkill(MathSkill):
    default_input_key = "formal.coq_candidate"
    default_output_key = "formal.coq_result"
    required_tool = "coqc"
    tool_name = "coq"

    skill_meta = SkillMeta(
        name="coq_check",
        version="0.1.0",
        description="Check a Coq source file with coqc.",
        author="NeuroCore Contributors",
        provides=["formal.coq_result"], consumes=["formal.coq_candidate"],
        tags=["math", "formalization", "coq", "verify"],
        config_schema={"properties": {
            "input_key": {"type": "string"}, "output_key": {"type": "string"},
            "timeout_seconds": {"type": "integer"},
        }},
    )

    async def _compute(self, payload: Any, context: FlowContext) -> dict[str, Any]:
        code = _source(payload, "candidate")
        if not code:
            return self.envelope(STATUS_ERROR, error="no Coq source provided")
        fd, path = tempfile.mkstemp(prefix="nc-coq-", suffix=".v")
        with os.fdopen(fd, "w") as fh:
            fh.write(code)
        res = run_cli(["coqc", path], timeout=self.timeout)
        if res.timed_out:
            self.port(context, "failed")
            return self.envelope(STATUS_TIMEOUT, error="coqc timed out", result={"verified": False})
        log = (res.stdout + "\n" + res.stderr).strip()
        verified = res.returncode == 0
        self.port(context, "verified" if verified else "repair_needed")
        return self.envelope(
            STATUS_PROVED if verified else STATUS_OK,
            result={"verified": verified, "errors": None if verified else log[:4000]},
            log=log[:4000],
        )
