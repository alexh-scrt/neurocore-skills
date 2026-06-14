"""Tests for PostgresSkill (DB call mocked via the _execute seam)."""
from __future__ import annotations

from flowengine import FlowContext
from neurocore_skill_postgres import PostgresSkill


def test_skill_meta():
    assert PostgresSkill.skill_meta.name == "postgres"
    assert "postgres_rows" in PostgresSkill.skill_meta.provides


async def test_process_returns_rows(monkeypatch):
    skill = PostgresSkill()
    skill.init({"dsn": "postgresql://x"})

    async def fake_execute(sql, params):
        assert "select" in sql.lower()
        return [{"id": 1, "name": "a"}]

    monkeypatch.setattr(skill, "_execute", fake_execute)
    ctx = FlowContext()
    ctx.set("sql", "SELECT * FROM t")
    out = await skill.process(ctx)
    assert out.get("postgres_rows")[0]["name"] == "a"


async def test_config_sql_default(monkeypatch):
    skill = PostgresSkill()
    skill.init({"dsn": "postgresql://x", "sql": "SELECT 1"})

    async def fake_execute(sql, params):
        return [{"?column?": 1}]

    monkeypatch.setattr(skill, "_execute", fake_execute)
    out = await skill.process(FlowContext())
    assert out.get("postgres_rows") == [{"?column?": 1}]


async def test_no_sql_returns_empty():
    skill = PostgresSkill()
    skill.init({"dsn": "postgresql://x"})
    out = await skill.process(FlowContext())
    assert out.get("postgres_rows") == []


async def test_error_sets_sentinel(monkeypatch):
    skill = PostgresSkill()
    skill.init({"dsn": "postgresql://x"})

    async def boom(sql, params):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(skill, "_execute", boom)
    ctx = FlowContext()
    ctx.set("sql", "SELECT 1")
    out = await skill.process(ctx)
    assert "error" in out.get("postgres_rows")
