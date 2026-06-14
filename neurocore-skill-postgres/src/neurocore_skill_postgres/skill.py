"""PostgresSkill — run a parameterized SQL query against PostgreSQL.

Reads ``sql`` (and optional ``sql_params``) from context (config provides
defaults) and writes returned rows to ``postgres_rows``.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from flowengine import FlowContext

from neurocore import AsyncSkill, SkillMeta

logger = logging.getLogger(__name__)


class PostgresSkill(AsyncSkill):
    """Async parameterized SQL execution against PostgreSQL (psycopg 3)."""

    skill_meta = SkillMeta(
        name="postgres",
        version="0.1.0",
        description="Run parameterized SQL against PostgreSQL",
        author="NeuroCore Contributors",
        requires=["psycopg[binary]>=3.1"],
        provides=["postgres_rows"],
        consumes=["sql", "sql_params"],
        tags=["database", "sql", "postgres"],
        config_schema={
            "properties": {
                "dsn": {"type": "string", "description": "Connection string."},
                "sql": {"type": "string", "description": "Default SQL (overridable)."},
            }
        },
    )

    def _resolve_dsn(self) -> str:
        return self.config.get("dsn", "") or os.environ.get("DATABASE_URL", "")

    async def _execute(self, sql: str, params: Any) -> list[dict[str, Any]]:
        """Execute ``sql`` and return rows as dicts (empty for non-SELECT)."""
        import psycopg
        from psycopg.rows import dict_row

        async with await psycopg.AsyncConnection.connect(
            self._resolve_dsn(), row_factory=dict_row
        ) as conn, conn.cursor() as cur:
            await cur.execute(sql, params)
            if cur.description is None:
                await conn.commit()
                return []
            return [dict(row) for row in await cur.fetchall()]

    async def process(self, context: FlowContext) -> FlowContext:
        sql = str(context.get("sql") or self.config.get("sql", ""))
        if not sql:
            logger.warning("PostgresSkill: no 'sql' provided.")
            context.set("postgres_rows", [])
            return context
        params = context.get("sql_params")
        try:
            context.set("postgres_rows", await self._execute(sql, params))
        except Exception as exc:  # noqa: BLE001
            logger.error("PostgresSkill query failed: %s", exc, exc_info=True)
            context.set("postgres_rows", {"error": str(exc)})
        return context
