"""The shipped blueprints load and resolve all skill references."""
from __future__ import annotations

from pathlib import Path

import pytest
from neurocore.runtime.blueprint import load_blueprint, validate_blueprint
from neurocore.skills.loader import discover_entry_points

BLUEPRINTS = Path(__file__).resolve().parents[1] / "blueprints"


@pytest.fixture(scope="module")
def registry():
    # Entry points include the installed neurocore-skill-math types.
    return discover_entry_points()


@pytest.mark.parametrize("name", [
    "lean-first-math-worker.flow.yaml",
    "math-proof-validation-worker.flow.yaml",
])
def test_blueprint_valid(name, registry):
    bp = load_blueprint(BLUEPRINTS / name)
    assert bp.flow.type == "graph"
    errors = validate_blueprint(bp, registry)
    assert errors == [], f"unresolved skills in {name}: {errors}"
