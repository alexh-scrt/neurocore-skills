# NeuroCore Component Lifecycle & Interface Design

This document details the initialization, execution, and termination lifecycles for each of the 14 NeuroCore skills. It guarantees that skills are properly initialized during static flow setup, execute context-specific tasks safely, and free resources from the process space upon task completion.

---

## 1. The Skill Lifecycle Protocol

Each skill conforms to the standard lifecycle hooks called by the NeuroCore/FlowEngine runner:

```
[Instantiation]
      │
      ▼
  init(config)        <-- Static flow setup (establish database connection, preload models)
      │
      ▼
  setup(context)      <-- Per-run state setup (read input parameters)
      │
      ▼
  process(context)    <-- Execution phase (perform SMT solver runs, query APIs)
      │
      ▼
  teardown(context)   <-- Clean up execution state, close clients
      │
      ▼
[Process Reclaimed]   <-- Destruction (garbage collection of loaded python modules/memories)
```

1. **`init(self, config)`**: Called once when the flow is built. Preloads static assets, API clients, and parameters.
2. **`setup(self, context)`**: Called before `process`. Readies step-level task scopes.
3. **`process(self, context)`**: Executes the task. Interacts with other skills via `neurogossip-agent-v3`.
4. **`teardown(self, context)`**: Called at exit. Closes open files, handles subprocess cleanup, terminates active API client sessions, and deletes memory-cached model parameters to release process space.

---

## 2. Component Design & Compliance

### 1. `start` (neurocore-skill-start)
* **Goal**: Validate and set up macro flow.
* **`init(config)`**: Loads validation schemas from `/home/ubuntu/neurocore/src/neurocore/runtime/blueprint.py`.
* **`process(context)`**:
  1. Reads `flow_yaml` and checks validation rules.
  2. Creates the execution workspace folder specified by `artifact_path`.
  3. Writes validation report to disk.
* **`teardown(context)`**: Clears file handles and workspace references.

### 2. `coordinator` (neurocore-skill-coordinator)
* **Goal**: Orchestrates task distribution and handles routing.
* **`init(config)`**: Configures dynamic task execution states and schedule trackers.
* **`process(context)`**:
  1. Calls `planner` to generate the step plan.
  2. Tracks worker assignments and step-level dependencies in `FlowContext`.
  3. Routes messages sequentially to workers based on step status.
* **`teardown(context)`**: Serializes final run state logs to the persistence directory and cleans up memory-mapped step trackers.

### 3. `planner` (neurocore-skill-planner)
* **Goal**: Generate step-by-step task flow plans.
* **`init(config)`**: Connects to the LLM agent model config (e.g. `planner_model`).
* **`process(context)`**:
  1. Contacts `researcher` to gather background topics.
  2. Compiles a list of execution steps (as described in the dynamic YAML structure).
  3. Cycles with `writer`, `reviewer`, and `judge` to refine steps.
* **`teardown(context)`**: Releases prompt templates and active LLM API handles.

### 4. `researcher` (neurocore-skill-researcher)
* **Goal**: Unified web and library search aggregator.
* **`init(config)`**: Initializes API tokens and connection pools for Tavily, Brave, and arXiv backends.
* **`process(context)`**:
  1. Orchestrates asynchronous API calls to `arxiv`, `tavily`, and `brave`.
  2. Deduplicates results, extracts markdown text summaries, and merges them.
* **`teardown(context)`**: Closes HTTPX client connection pools and releases sockets.

### 5. `arxiv` (neurocore-skill-arxiv)
* **Goal**: Query the arXiv academic API.
* **`init(config)`**: Sets up connection limits and rates.
* **`process(context)`**: Performs search queries against `arxiv.org` based on topic parameters.
* **`teardown(context)`**: Closes network connections.

### 6. `writer` (neurocore-skill-writer)
* **Goal**: Text and content generation.
* **`init(config)`**: Registers system writing prompt templates and injects target model configs.
* **`process(context)`**: Generates reports, plan scripts, or text sections based on input prompts and research.
* **`teardown(context)`**: Clears local generation context and frees LLM call memory.

### 7. `reviewer` (neurocore-skill-reviewer)
* **Goal**: Adversarial critique.
* **`init(config)`**: Preloads criticism criteria checklists.
* **`process(context)`**: Reviews drafts for accuracy, gaps, and formatting, outputting detailed critique reports.
* **`teardown(context)`**: Clears the criticism memory context.

### 8. `math_verifier` (neurocore-skill-math-verifier)
* **Goal**: Symbolic verification.
* **`init(config)`**: Preloads SymPy environment context and imports `z3-solver` instances.
* **`process(context)`**: Evaluates expressions using symbolic simplification and SMT checks, producing proofs or counterexamples.
* **`teardown(context)`**: Terminates and destroys Z3 solver context instances, reclaiming memory.

### 9. `judge` (neurocore-skill-judge)
* **Goal**: Quality gatekeeping evaluation.
* **`init(config)`**: Injects evaluation score metrics and success criteria parameters.
* **`process(context)`**: Compares work results against reviews/verifications, deciding `APPROVED` or `REJECTED`.
* **`teardown(context)`**: Reclaims evaluation log buffers.

### 10. `human` (neurocore-skill-human)
* **Goal**: Human approval checkpoint.
* **`init(config)`**: Sets up interactive console/web prompt callbacks.
* **`process(context)`**: Suspends flow execution, alerts user for input, and resumes once approved.
* **`teardown(context)`**: Detaches console readers and event listeners.

### 11. `worker` (neurocore-skill-worker)
* **Goal**: Performs specific task steps.
* **`init(config)`**: Resolves task parameters and preloads worker configurations.
* **`process(context)`**: Executes task instructions using nested gossip loops (researcher $\to$ reviewer $\to$ verifier $\to$ judge).
* **`teardown(context)`**: Destroys step-level execution instances and cleans up temporary local files.

### 12. `end` (neurocore-skill-end)
* **Goal**: Closes workflow and returns results.
* **`init(config)`**: Prepares final output serialization formatters.
* **`process(context)`**: Packages outputs and passes final execution context back to the master agent.
* **`teardown(context)`**: Runs garbage collection to ensure the process space is completely cleared.

### 13. `error` (neurocore-skill-error)
* **Goal**: Flow exception handler.
* **`init(config)`**: Injects alert handlers (e.g. Telegram notification channels).
* **`process(context)`**: Collects error dumps, posts failure alerts, and cleans up runs.
* **`teardown(context)`**: Flushes error reporting sockets.

---

## 3. Reclaiming the Process Space

To ensure that the higher-order agent can free all NeuroCore skills from memory and process handles upon termination:

1. **Explicit Teardown Cascading**:
   * When `flow-end` or `flow-error-handler` completes, it executes a recursive `teardown()` across all components in the executor registry.
2. **Subprocess/Port Reclaim**:
   * In `teardown`, skills are required to call `.close()`, destroy active C-level objects (like Z3 Solver contexts), and stop any spawned subprocesses.
3. **Python Module Unloading (Garbage Collection)**:
   * `flow-end` invokes `gc.collect()` to free any unreferenced model arrays, network sockets, or context dictionaries, leaving the process space completely clean.
