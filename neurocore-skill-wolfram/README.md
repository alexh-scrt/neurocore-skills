# neurocore-skill-wolfram

Computational-knowledge answers for NeuroCore via
[Wolfram|Alpha](https://products.wolframalpha.com/short-answers-api/).

```bash
pip install neurocore-skill-wolfram
export WOLFRAM_APP_ID=...
```

```yaml
components:
  - name: compute
    type: wolfram
flow:
  type: sequential
  steps:
    - component: compute
```

Reads `wolfram_query`; writes `wolfram_result` (a plain-text answer string).
