# neurocore-skill-brave

Web search for NeuroCore via the [Brave Search API](https://brave.com/search/api/).

```bash
pip install neurocore-skill-brave
export BRAVE_API_KEY=...
```

```yaml
components:
  - name: search
    type: brave
    config:
      count: 5
flow:
  type: sequential
  steps:
    - component: search
```

Reads `brave_query` from context; writes `brave_results` (a list of result
dicts). Set the key via `--data brave_query="..."` or an upstream skill.
