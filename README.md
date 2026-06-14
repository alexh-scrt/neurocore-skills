# neurocore-skills

A monorepo of installable [NeuroCore](https://github.com/alexh-scrt/neurocore)
skills — pip-installable agent capabilities. Install what you need; NeuroCore
discovers them automatically.

```bash
pip install neurocore-skill-tavily neurocore-skill-qdrant
neurocore skill list          # newly installed skills appear here
neurocore run blueprints/research.flow.yaml
```

## Skills in this repo

| Package | Skill `type` | What it does |
|---------|--------------|--------------|
| `neurocore-skill-tavily`   | `tavily`   | Smart web search via the Tavily API |
| `neurocore-skill-brave`    | `brave`    | Web search via the Brave Search API |
| `neurocore-skill-wolfram`  | `wolfram`  | Computational answers via Wolfram\|Alpha |
| `neurocore-skill-qdrant`   | `qdrant`   | Vector similarity search over Qdrant |
| `neurocore-skill-postgres` | `postgres` | Run parameterized SQL against PostgreSQL |
| `neurocore-skill-ollama`   | `ollama`   | Text generation via a local Ollama server |
| `neurocore-skill-telegram` | `telegram` | Send Telegram messages from a flow |

## The skill package convention

Every NeuroCore skill package follows the same shape (see any subdir):

```
neurocore-skill-<name>/
├── pyproject.toml
├── README.md
└── src/neurocore_skill_<name>/
    ├── __init__.py        # exports the Skill subclass
    └── skill.py
└── tests/test_skill.py
```

Two rules make discovery "just work":

1. **Naming** — distribution `neurocore-skill-<name>`, import package
   `neurocore_skill_<name>` (kebab → snake).
2. **Entry point** — register under the `neurocore.skills` group:

   ```toml
   [project.entry-points."neurocore.skills"]
   <name> = "neurocore_skill_<name>:<ClassName>Skill"
   ```

   ⚠️ The group is `neurocore.skills` (not `neurocore_ai.skills`).

The class subclasses `Skill`/`AsyncSkill`, declares a `skill_meta = SkillMeta(...)`
(name, `provides`, `consumes`, `config_schema`, `tags`), and implements
`process(context) -> context`. See
[the skill-authoring guide](https://neurocore.readthedocs.io/skill-authoring.html).

## Development

Each package is independent. To work on one:

```bash
cd neurocore-skill-brave
pip install -e ".[dev]"
pytest
```
