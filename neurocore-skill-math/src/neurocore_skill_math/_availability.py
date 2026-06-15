"""Detect which math tools (CLIs and Python libs) are available at runtime.

Skills use this to degrade gracefully when a backend is not installed, and the
``python -m neurocore_skill_math.check`` command prints a full report.
"""
from __future__ import annotations

import importlib.util
import shutil

# CLI executables expected on PATH (Ubuntu installer provides these).
CLI_TOOLS: list[str] = [
    "gp",        # PARI/GP
    "gap",       # GAP
    "sage",      # SageMath (or via docker)
    "docker",    # for the SageMath container fallback
    "z3",        # z3 CLI (the skill prefers the python binding)
    "cvc5",      # cvc5 CLI
    "vampire",
    "eprover",
    "prover9",
    "mace4",
    "lean",
    "lake",
    "isabelle",
    "coqc",
]

# Python libraries used directly by skills.
PY_LIBS: list[str] = ["sympy", "mpmath", "z3", "cvc5", "numpy", "scipy", "networkx"]


def tool_available(name: str) -> bool:
    """True if a CLI executable is on PATH."""
    return shutil.which(name) is not None


def lib_available(module: str) -> bool:
    """True if a Python module can be imported."""
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


def availability_report() -> dict[str, dict[str, bool]]:
    """Return {'cli': {tool: bool}, 'lib': {module: bool}}."""
    return {
        "cli": {t: tool_available(t) for t in CLI_TOOLS},
        "lib": {m: lib_available(m) for m in PY_LIBS},
    }
