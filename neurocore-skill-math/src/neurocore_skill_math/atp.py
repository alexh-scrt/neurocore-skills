"""Group 3/4 — automated theorem provers and finite-model search.

- ``vampire_prove_tptp`` / ``eprover_prove_tptp`` — first-order ATP on TPTP input.
- ``prover9_prove`` — Prover9 (its own syntax).
- ``mace4_countermodel`` — Mace4 finite-model search (counterexamples).

Provers set port ``proof_found`` / ``no_proof``; Mace4 sets ``counterexample_found`` /
``no_counterexample``.
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
    STATUS_REFUTED,
    STATUS_TIMEOUT,
    STATUS_UNKNOWN,
    MathSkill,
)
from neurocore_skill_math._formats import as_prover9, as_tptp
from neurocore_skill_math._run import run_cli

_TPTP_SCHEMA = {"properties": {
    "input_key": {"type": "string"}, "output_key": {"type": "string"},
    "premises_key": {"type": "string"}, "timeout_seconds": {"type": "integer"},
}}


def _szs_verdict(text: str) -> str:
    """Map prover stdout (SZS ontology / common phrases) to proved/disproved/unknown."""
    t = text.lower()
    if ("refutation found" in t or "szs status theorem" in t
            or "szs status unsatisfiable" in t or "proof found" in t
            or "theorem proved" in t):
        return "proved"
    if ("countersatisfiable" in t or "szs status satisfiable" in t
            or "search failed" in t):
        return "disproved"
    return "unknown"


class _TptpProver(MathSkill):
    default_input_key = "math.normalized"
    cli: str = ""  # subclass sets the executable

    def _write_tmp(self, content: str, suffix: str) -> str:
        fd, path = tempfile.mkstemp(prefix="nc-atp-", suffix=suffix)
        with os.fdopen(fd, "w") as fh:
            fh.write(content)
        return path

    def _route_proof(self, context: FlowContext, verdict: str, log: str) -> dict[str, Any]:
        if verdict == "proved":
            self.port(context, "proof_found")
            return self.envelope(STATUS_PROVED, result={"proof_found": True}, log=log[:4000])
        self.port(context, "no_proof")
        status = STATUS_OK if verdict == "disproved" else STATUS_UNKNOWN
        return self.envelope(status, result={"proof_found": False, "verdict": verdict},
                             log=log[:4000])


class VampireProveTptpSkill(_TptpProver):
    default_output_key = "proof.vampire"
    required_tool = "vampire"
    cli = "vampire"
    tool_name = "vampire"

    skill_meta = SkillMeta(
        name="vampire_prove_tptp",
        version="0.1.0",
        description="Prove a TPTP first-order conjecture with Vampire.",
        author="NeuroCore Contributors",
        provides=["proof.vampire"], consumes=["math.normalized", "proof.premises"],
        tags=["math", "atp", "tptp", "vampire"], config_schema=_TPTP_SCHEMA,
    )

    async def _compute(self, payload: Any, context: FlowContext) -> dict[str, Any]:
        tptp = as_tptp(payload)
        if not tptp:
            return self.envelope(STATUS_ERROR, error="no TPTP input provided")
        path = self._write_tmp(tptp, ".p")
        res = run_cli(["vampire", "-t", str(int(self.timeout)), path], timeout=self.timeout + 5)
        if res.timed_out:
            self.port(context, "no_proof")
            return self.envelope(STATUS_TIMEOUT, error="vampire timed out")
        return self._route_proof(context, _szs_verdict(res.stdout), res.stdout)


class EproverProveTptpSkill(_TptpProver):
    default_output_key = "proof.eprover"
    required_tool = "eprover"
    cli = "eprover"
    tool_name = "eprover"

    skill_meta = SkillMeta(
        name="eprover_prove_tptp",
        version="0.1.0",
        description="Prove a TPTP first-order conjecture with the E prover.",
        author="NeuroCore Contributors",
        provides=["proof.eprover"], consumes=["math.normalized", "proof.premises"],
        tags=["math", "atp", "tptp", "eprover"], config_schema=_TPTP_SCHEMA,
    )

    async def _compute(self, payload: Any, context: FlowContext) -> dict[str, Any]:
        tptp = as_tptp(payload)
        if not tptp:
            return self.envelope(STATUS_ERROR, error="no TPTP input provided")
        path = self._write_tmp(tptp, ".p")
        res = run_cli(
            ["eprover", "--auto", "--tptp3-format", f"--cpu-limit={int(self.timeout)}", path],
            timeout=self.timeout + 5,
        )
        if res.timed_out:
            self.port(context, "no_proof")
            return self.envelope(STATUS_TIMEOUT, error="eprover timed out")
        return self._route_proof(context, _szs_verdict(res.stdout), res.stdout)


class Prover9ProveSkill(_TptpProver):
    default_output_key = "proof.prover9"
    required_tool = "prover9"
    cli = "prover9"
    tool_name = "prover9"

    skill_meta = SkillMeta(
        name="prover9_prove",
        version="0.1.0",
        description="Prove a conjecture with Prover9 (Prover9 input syntax).",
        author="NeuroCore Contributors",
        provides=["proof.prover9"], consumes=["math.normalized", "proof.premises"],
        tags=["math", "atp", "prover9"], config_schema=_TPTP_SCHEMA,
    )

    async def _compute(self, payload: Any, context: FlowContext) -> dict[str, Any]:
        deck = as_prover9(payload)
        if not deck:
            return self.envelope(STATUS_ERROR, error="no Prover9 input provided")
        res = run_cli(["prover9"], stdin=deck, timeout=self.timeout)
        if res.timed_out:
            self.port(context, "no_proof")
            return self.envelope(STATUS_TIMEOUT, error="prover9 timed out")
        return self._route_proof(context, _szs_verdict(res.stdout), res.stdout)


class Mace4CountermodelSkill(MathSkill):
    default_input_key = "math.normalized"
    default_output_key = "counterexamples.mace4"
    required_tool = "mace4"
    tool_name = "mace4"

    skill_meta = SkillMeta(
        name="mace4_countermodel",
        version="0.1.0",
        description="Search for a finite countermodel with Mace4.",
        author="NeuroCore Contributors",
        provides=["counterexamples.mace4"], consumes=["math.normalized"],
        tags=["math", "counterexample", "finite-model", "mace4"],
        config_schema={"properties": {
            "input_key": {"type": "string"}, "output_key": {"type": "string"},
            "timeout_seconds": {"type": "integer"}, "max_domain_size": {"type": "integer"},
        }},
    )

    async def _compute(self, payload: Any, context: FlowContext) -> dict[str, Any]:
        deck = as_prover9(payload)
        if not deck:
            return self.envelope(STATUS_ERROR, error="no Mace4 input provided")
        n = int(self.config.get("max_domain_size", 8))
        res = run_cli(["mace4", "-n", str(n)], stdin=deck, timeout=self.timeout)
        if res.timed_out:
            self.port(context, "no_counterexample")
            return self.envelope(STATUS_TIMEOUT, error="mace4 timed out")
        found = "model" in res.stdout.lower() and "exiting with" in res.stdout.lower()
        if found:
            self.port(context, "counterexample_found")
            return self.envelope(STATUS_REFUTED, result={"countermodel": res.stdout.strip()},
                                 counterexample_found=True)
        self.port(context, "no_counterexample")
        return self.envelope(STATUS_OK, result={"countermodel": None},
                             counterexample_found=False)
