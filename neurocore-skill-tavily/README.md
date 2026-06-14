# neurocore-skill-tavily

Smart web search for NeuroCore via the [Tavily API](https://tavily.com).

```bash
pip install neurocore-skill-tavily
export TAVILY_API_KEY=tvly-...
```

```yaml
components:
  - name: search
    type: tavily
    config:
      max_results: 5
      search_depth: advanced
flow:
  type: sequential
  steps:
    - component: search
```

Reads `tavily_query`; writes `tavily_results` (list of `{title, url, content}`).
