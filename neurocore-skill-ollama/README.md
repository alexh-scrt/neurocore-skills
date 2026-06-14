# neurocore-skill-ollama

Direct text generation against a local [Ollama](https://ollama.com) server.

```bash
pip install neurocore-skill-ollama
ollama serve & ; ollama pull llama3.2
```

```yaml
components:
  - name: generate
    type: ollama
    config:
      model: llama3.2
      system: "You are concise."
flow:
  type: sequential
  steps:
    - component: generate
```

Reads `prompt`; writes `ollama_response` (the generated text).

> For chat-style LLM access from skills with `requires_llm=True`, prefer
> NeuroCore's built-in `ollama` **provider** (`llm.provider: ollama`). This
> skill is a provider-free direct call to `/api/generate`.
