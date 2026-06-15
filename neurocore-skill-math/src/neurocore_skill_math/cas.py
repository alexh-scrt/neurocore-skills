"""Group 2 — computer-algebra backends invoked as external processes.

- ``pari_gp_number_theory`` — PARI/GP (`gp`), number theory.
- ``gap_group_theory`` — GAP (`gap`), group theory.
- ``sagemath_compute`` — SageMath, via local `sage` or a sandboxed Docker container.

All take a script string (or a dict with ``script``/``code``) and return stdout.
"""
from __future__ import annotations

import os
import tempfile
from typing import Any

from flowengine import FlowContext
from neurocore import SkillMeta

from neurocore_skill_math._availability import tool_available
from neurocore_skill_math._base import STATUS_ERROR, STATUS_OK, STATUS_TIMEOUT, MathSkill
from neurocore_skill_math._run import docker_cmd, run_cli


def _script(payload: Any, *keys: str) -> str:
    if isinstance(payload, str):
        return payload
    if hasattr(payload, "get"):
        for k in (*keys, "script", "code", "source", "normalized"):
            v = payload.get(k)
            if isinstance(v, str) and v.strip():
                return v
    return str(payload or "")


class PariGpNumberTheorySkill(MathSkill):
    default_input_key = "math.normalized"
    default_output_key = "evidence.pari"
    required_tool = "gp"
    tool_name = "pari_gp"

    skill_meta = SkillMeta(
        name="pari_gp_number_theory",
        version="0.1.0",
        description="Run PARI/GP number-theory computations.",
        author="NeuroCore Contributors",
        provides=["evidence.pari"],
        consumes=["math.normalized"],
        tags=["math", "number-theory", "cas", "pari"],
        config_schema={"properties": {
            "input_key": {"type": "string"}, "output_key": {"type": "string"},
            "timeout_seconds": {"type": "integer"},
        }},
    )

    async def _compute(self, payload: Any, context: FlowContext) -> dict[str, Any]:
        script = _script(payload, "gp")
        if not script:
            return self.envelope(STATUS_ERROR, error="no GP script provided")
        res = run_cli(["gp", "-q"], stdin=script, timeout=self.timeout)
        if res.timed_out:
            return self.envelope(STATUS_TIMEOUT, error="gp timed out", log=res.stderr)
        return self.envelope(STATUS_OK, result={"output": res.stdout.strip()},
                             log=res.stderr.strip())


class GapGroupTheorySkill(MathSkill):
    default_input_key = "math.normalized"
    default_output_key = "evidence.gap"
    required_tool = "gap"
    tool_name = "gap"

    skill_meta = SkillMeta(
        name="gap_group_theory",
        version="0.1.0",
        description="Run GAP group-theory computations.",
        author="NeuroCore Contributors",
        provides=["evidence.gap"],
        consumes=["math.normalized"],
        tags=["math", "group-theory", "cas", "gap"],
        config_schema={"properties": {
            "input_key": {"type": "string"}, "output_key": {"type": "string"},
            "timeout_seconds": {"type": "integer"},
        }},
    )

    async def _compute(self, payload: Any, context: FlowContext) -> dict[str, Any]:
        script = _script(payload, "gap")
        if not script:
            return self.envelope(STATUS_ERROR, error="no GAP script provided")
        # -q quiet, run script from stdin, then quit.
        res = run_cli(["gap", "-q", "-b"], stdin=script + "\nQUIT;\n", timeout=self.timeout)
        if res.timed_out:
            return self.envelope(STATUS_TIMEOUT, error="gap timed out", log=res.stderr)
        return self.envelope(STATUS_OK, result={"output": res.stdout.strip()},
                             log=res.stderr.strip())


class SagemathComputeSkill(MathSkill):
    default_input_key = "math.normalized"
    default_output_key = "evidence.sage"
    tool_name = "sagemath"

    skill_meta = SkillMeta(
        name="sagemath_compute",
        version="0.1.0",
        description="Run a SageMath script (local sage or a sandboxed Docker container).",
        author="NeuroCore Contributors",
        provides=["evidence.sage"],
        consumes=["math.normalized"],
        tags=["math", "cas", "sagemath"],
        config_schema={"properties": {
            "input_key": {"type": "string"}, "output_key": {"type": "string"},
            "timeout_seconds": {"type": "integer"},
            "docker_image": {"type": "string"},
            "memory": {"type": "string"}, "cpus": {"type": "string"},
        }},
    )

    def is_available(self) -> bool:
        return tool_available("sage") or tool_available("docker")

    async def _compute(self, payload: Any, context: FlowContext) -> dict[str, Any]:
        script = _script(payload, "sage")
        if not script:
            return self.envelope(STATUS_ERROR, error="no Sage script provided")
        if tool_available("sage"):
            res = run_cli(["sage", "-c", script], timeout=self.timeout)
        else:
            # Sandboxed container: write script to a temp dir mounted read-only.
            tmp = tempfile.mkdtemp(prefix="nc-sage-")
            path = os.path.join(tmp, "script.sage")
            with open(path, "w") as fh:
                fh.write(script)
            image = self.config.get("docker_image", "sagemath/sagemath:latest")
            cmd = docker_cmd(
                image, ["sage", "/work/script.sage"],
                memory=self.config.get("memory", "4g"),
                cpus=self.config.get("cpus", "2"),
                mounts=[(tmp, "/work")],
            )
            res = run_cli(cmd, timeout=self.timeout)
        if res.timed_out:
            return self.envelope(STATUS_TIMEOUT, error="sage timed out", log=res.stderr)
        return self.envelope(STATUS_OK, result={"output": res.stdout.strip()},
                             log=res.stderr.strip())
