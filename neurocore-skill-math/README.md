# neurocore-skill-math

A **math-proof toolchain** for [NeuroCore](https://github.com/alexh-scrt/neurocore):
one package exposing many small, composable skills that wrap computer-algebra
systems, SMT solvers, automated theorem provers, and formal proof assistants. A
supervisor agent / FlowEngine blueprint composes them into proof-search and
proof-validation chains.

```bash
pip install neurocore-skill-math          # pulls sympy, mpmath, z3-solver
pip install "neurocore-skill-math[cvc5]"  # + cvc5 SMT backend (optional)
```

Most external engines (Lean, Vampire, Isabelle, Coq, SageMath, GAP, PARI/GP, …)
are **not** Python packages — install them with the provided script
(`scripts/install_math_tools.sh`, Ubuntu 24.04) and check what's available:

```bash
python -m neurocore_skill_math.check      # prints a tool-availability report
```

Every skill **detects whether its backend is installed** and degrades gracefully
(status `tool_unavailable`) rather than crashing a flow.

## Skills

| `type` | Group | Backend | Reads → writes |
|--------|-------|---------|----------------|
| `math_problem_parser` | prep | LLM | `problem` → `math.parsed` |
| `math_domain_classifier` | prep | LLM | `math.parsed` → `math.domain` |
| `math_statement_normalizer` | prep | LLM | `math.parsed` → `math.normalized` |
| `sympy_simplify` / `sympy_solve` / `sympy_calculus` | symbolic | SymPy | `math.normalized` → `evidence.sympy` |
| `mpmath_high_precision_check` | numeric | mpmath | `math.normalized` → `evidence.numeric` |
| `pari_gp_number_theory` | CAS | `gp` | `math.normalized` → `evidence.pari` |
| `gap_group_theory` | CAS | `gap` | `math.normalized` → `evidence.gap` |
| `sagemath_compute` | CAS | `sage`/Docker | `math.normalized` → `evidence.sage` |
| `z3_smt_check` | SMT | z3 | `math.normalized` → `counterexamples.z3` |
| `cvc5_smt_check` | SMT | cvc5 | `math.normalized` → `counterexamples.cvc5` |
| `mace4_countermodel` | counterexample | `mace4` | `math.normalized` → `counterexamples.mace4` |
| `vampire_prove_tptp` / `eprover_prove_tptp` | ATP | `vampire`/`eprover` | `math.normalized` → `proof.*` |
| `prover9_prove` | ATP | `prover9` | `math.normalized` → `proof.prover9` |
| `llm_proof_planner` | planning | LLM | evidence → `proof.strategy` |
| `theorem_retriever` | planning | LLM | `proof.strategy` → `proof.premises` |
| `lean4_formalize_statement` | formal | LLM | `math.normalized` → `formal.lean_candidate` |
| `lean4_check` | formal | `lean`/`lake` | `formal.lean_candidate` → `formal.lean_result` |
| `lean4_repair` | formal | LLM | `formal.lean_candidate` + errors → `formal.lean_candidate` |
| `isabelle_check_theory` | formal | `isabelle` | `formal.isabelle_candidate` → `formal.isabelle_result` |
| `coq_check` | formal | `coqc` | `formal.coq_candidate` → `formal.coq_result` |
| `proof_report_builder` | report | — | all envelopes → `validation_status` / `final_answer` / `proof_artifacts` |

### Result envelope & ports

Each skill writes a uniform envelope:
`{status, tool, available, result, log, error, duration_ms}` with
`status ∈ {ok, proved, refuted, unknown, tool_unavailable, error, timeout}`.

Skills set **output ports** so graph blueprints can route:
- SMT / Mace4: `counterexample_found` / `no_counterexample`
- ATP: `proof_found` / `no_proof`
- Lean/Isabelle/Coq check: `verified` / `repair_needed` / `failed`
- domain classifier: `number_theory` / `group_theory` / …

All skills take configurable `input_key` / `output_key` (the doc's dotted-key
contract, e.g. `evidence.sympy`), so the same skill can be wired into different
positions in a chain.

## Blueprints

`blueprints/` ships two reference proof workers from the design:
- `lean-first-math-worker.flow.yaml` — a focused parse → explore → refute →
  formalize → verify → repair → report loop.
- `math-proof-validation-worker.flow.yaml` — the full fan-out across CAS/SMT/ATP
  then Lean/Isabelle/Coq validation.

> **Graph routing.** These workers use edge **ports**, edge **conditions**, and a
> Lean **repair loop**. With `neurocore-ai>=0.4.0` (on `flowengine>=0.6.0`),
> NeuroCore routes such graph flows through flowengine's `GraphExecutor`, which
> honors port/condition gating and cyclic `max_iterations` — so the conditional
> early-exits and the repair loop execute as drawn. Plain DAGs (no
> ports/conditions/cycles) still use the concurrent layer executor. On older
> NeuroCore the skills' ports are simply ignored (all reachable nodes run).

## Convention

Standard NeuroCore skill package: entry-point group `neurocore.skills`, import
package `neurocore_skill_math`, kebab distribution `neurocore-skill-math`. See the
[skill-authoring guide](https://neurocore.readthedocs.io/skill-authoring.html).
