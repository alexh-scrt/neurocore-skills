# neurocore-skill-postgres

Run parameterized SQL against PostgreSQL from a NeuroCore flow (psycopg 3).

```bash
pip install neurocore-skill-postgres
export DATABASE_URL=postgresql://user:pass@localhost/db
```

```yaml
components:
  - name: query
    type: postgres
    config:
      sql: "SELECT id, name FROM users WHERE active = %s"
flow:
  type: sequential
  steps:
    - component: query
```

Provide `sql` (and optional `sql_params`) via config or context. Results are
written to `postgres_rows` (a list of row dicts; empty list for non-SELECT
statements, which are committed).

> Use parameterized queries (`%s` placeholders + `sql_params`) — never string
> interpolation — to avoid SQL injection.
