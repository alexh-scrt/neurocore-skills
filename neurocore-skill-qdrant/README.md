# neurocore-skill-qdrant

Vector similarity search for NeuroCore over [Qdrant](https://qdrant.tech).

```bash
pip install neurocore-skill-qdrant
docker run -p 6333:6333 qdrant/qdrant
```

```yaml
components:
  - name: retrieve
    type: qdrant
    config:
      collection: documents
      top_k: 5
flow:
  type: sequential
  steps:
    - component: retrieve
```

Reads `query_vector` (a list of floats from your embedder); writes
`qdrant_results` (a list of `{id, score, payload}`).
