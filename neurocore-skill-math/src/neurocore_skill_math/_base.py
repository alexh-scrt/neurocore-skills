"""Shared base for all math skills.

``MathSkill`` standardizes:
- configurable IO keys (``input_key`` / ``output_key`` + extras), per the design doc;
- a uniform **result envelope** every skill writes to context;
- **availability detection** + graceful degradation (never crash the flow when a
  backend tool/lib is missing);
- **port** helpers so skills can drive graph routing.

Concrete skills subclass this, set ``default_input_key`` / ``default_output_key`` /
``required_tool`` / ``required_lib`` / ``tool_name``, and implement ``_compute``.
"""
from __future__ import annotations

import time
from typing import Any

from flowengine import FlowContext
from neurocore import AsyncSkill

from neurocore_skill_math._availability import lib_available, tool_available

# Envelope status values.
STATUS_OK = "ok"
STATUS_REFUTED = "refuted"
STATUS_PROVED = "proved"
STATUS_UNKNOWN = "unknown"
STATUS_UNAVAILABLE = "tool_unavailable"
STATUS_ERROR = "error"
STATUS_TIMEOUT = "timeout"


class MathSkill(AsyncSkill):
    """Base class for math-toolchain skills (not registered itself)."""

    # Subclasses override these.
    default_input_key: str = "math.normalized"
    default_output_key: str = "math.result"
    required_tool: str | None = None  # CLI executable to check on PATH
    required_lib: str | None = None  # importable module to check
    tool_name: str = "math"

    def init(self, config: dict[str, Any]) -> None:
        super().init(config)
        self.in_key: str = self.config.get("input_key", self.default_input_key)
        self.out_key: str = self.config.get("output_key", self.default_output_key)
        self.timeout: float = float(self.config.get("timeout_seconds", 30))

    # -- availability ------------------------------------------------------
    def is_available(self) -> bool:
        tool_ok = not self.required_tool or tool_available(self.required_tool)
        lib_ok = not self.required_lib or lib_available(self.required_lib)
        return tool_ok and lib_ok

    def health_check(self) -> bool:
        return self.is_initialized and self.is_available()

    # -- execution ---------------------------------------------------------
    async def process(self, context: FlowContext) -> FlowContext:  # type: ignore[override]
        if not self.is_available():
            missing = self.required_tool or self.required_lib or self.tool_name
            self._write(
                context,
                self.envelope(
                    STATUS_UNAVAILABLE,
                    available=False,
                    error=f"{missing!r} is not installed; skill skipped.",
                ),
            )
            self.port(context, "tool_unavailable")
            return context

        payload = context.get(self.in_key)
        start = time.perf_counter()
        try:
            env = await self._compute(payload, context)
        except Exception as exc:  # noqa: BLE001 — degrade, don't crash the flow
            env = self.envelope(STATUS_ERROR, error=str(exc))
        env.setdefault("duration_ms", round((time.perf_counter() - start) * 1000, 2))
        self._write(context, env)
        return context

    async def _compute(self, payload: Any, context: FlowContext) -> dict[str, Any]:
        """Run the skill's work and return a result envelope. May also set ports."""
        raise NotImplementedError

    # -- helpers -----------------------------------------------------------
    def envelope(
        self,
        status: str,
        *,
        result: Any = None,
        log: str = "",
        error: str | None = None,
        available: bool = True,
        **extra: Any,
    ) -> dict[str, Any]:
        return {
            "status": status,
            "tool": self.tool_name,
            "available": available,
            "result": result,
            "log": log,
            "error": error,
            **extra,
        }

    def _write(self, context: FlowContext, env: dict[str, Any]) -> None:
        context.set(self.out_key, env)

    def port(self, context: FlowContext, name: str) -> None:
        self.set_output_port(context, name)
