"""Assemble solver inputs (SMT-LIB, TPTP) from skill payloads.

A payload may be a ready-made source string, or a structured dict carrying the
source under a known key (``smtlib`` / ``tptp`` / ``prover9``). Skills accept both
so an upstream LLM/normalizer can emit either form.
"""
from __future__ import annotations

from typing import Any


def _coerce(payload: Any, *keys: str) -> str | None:
    """Pull a source string out of a payload (raw string or dict with one of keys)."""
    if isinstance(payload, str):
        return payload
    if hasattr(payload, "get"):  # dict / DotDict
        for k in keys:
            v = payload.get(k)
            if isinstance(v, str) and v.strip():
                return v
    return None


def as_smtlib(payload: Any) -> str | None:
    """Return an SMT-LIB v2 script from the payload, or None if not provided.

    Ensures a ``(check-sat)`` is present so the solver actually runs.
    """
    src = _coerce(payload, "smtlib", "smt", "source")
    if src is None:
        return None
    if "(check-sat)" not in src:
        src = src.rstrip() + "\n(check-sat)\n"
    return src


def as_tptp(payload: Any) -> str | None:
    """Return a TPTP problem string from the payload, or None."""
    return _coerce(payload, "tptp", "fof", "source")


def as_prover9(payload: Any) -> str | None:
    """Return a Prover9/Mace4 input deck from the payload, or None."""
    return _coerce(payload, "prover9", "mace4", "source")


def parse_smt_result(stdout: str) -> str:
    """Map raw solver stdout to 'sat' | 'unsat' | 'unknown'."""
    text = stdout.strip().lower()
    if "unsat" in text:
        return "unsat"
    if "sat" in text:
        return "sat"
    return "unknown"
