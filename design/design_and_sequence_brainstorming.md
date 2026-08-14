# NeuroCore Skills Architecture & Sequence Design (Finalized & Refined)

This document contains the refined architecture, interaction sequence, and design patterns for the new NeuroCore planning and execution skills. It details the relationship between **Macro-Orchestration (Blueprints)** and **Micro-Orchestration (Gossip Routing)**.

---

## 1. Architectural Layers

To ensure scalability and decouple individual skill logic from rigid layout blueprints, the system operates on two distinct execution layers:

### Layer 1: Macro-Orchestration (The FlowEngine Blueprint)
* The top-level blueprint processed by NeuroCore is kept clean and simple: **`start` $\to$ `coordinator` $\to$ `end`**. 
* The `coordinator` functions as the general contractor. It executes in a single long-running flow state, preventing state explosion in the top-level orchestrator.
* If a critical failure happens, the flow routes to `error`.

### Layer 2: Micro-Orchestration (Peer-to-Peer Gossip)
* Internal sub-flows (e.g., Planner loop, Worker refinement loop) are routed dynamically using **`neurogossip-agent-v3`** messaging.
* The routing order, targets, and conditions are described in a **Dynamic Routing Table** (YAML) compiled by the Planner and passed inside the `FlowContext`.
* Skills read the routing instructions from the context, perform their logic, and publish their results back to the next peer in the list.

---

## 2. End-to-End Sequence Diagram

The diagram below shows how a task runs through validation, planning, execution, verification, and completion cycles, utilizing both gossip routing and human checkpoints.

```mermaid
sequenceDiagram
    autonumber
    actor Master as Master Agent (Higher Order)
    participant Start as neurocore-skill-start
    participant Coord as neurocore-skill-coordinator
    participant Planner as neurocore-skill-planner
    participant Research as neurocore-skill-researcher
    participant Writer as neurocore-skill-writer
    participant Reviewer as neurocore-skill-reviewer
    participant Verifier as neurocore-skill-math-verifier
    participant Judge as neurocore-skill-judge
    participant Human as neurocore-skill-human
    participant Worker as neurocore-skill-worker
    participant Error as neurocore-skill-error
    participant End as neurocore-skill-end

    Note over Master, Start: Phase 1: Initiation (Macro Layer)
    Master->>Start: Pass Flow YAML + Task Prompt
    activate Start
    alt YAML is Invalid
        Start-->>Error: Forward parsing/validation error
        Error-->>Master: Handle & notify error
    else YAML is Valid
        Start->>Coord: Forward parsed task & configuration
    end
    deactivate Start

    Note over Coord, Planner: Phase 2: Planning Loop (Micro Gossip Layer)
    activate Coord
    Coord->>Planner: Request detailed execution plan (via neurogossip)
    activate Planner
    
    Planner->>Research: Gather context / literature search
    Research-->>Planner: Search results (arXiv + Tavily + Brave)
    Planner->>Writer: Delegate plan drafting with research payload
    
    loop Refinement Cycle (Up to NEUROCORE_CYCLE_CAP times)
        Writer->>Writer: Formulate plan & save draft to configured disk path
        Writer->>Reviewer: Request adversarial plan review
        Reviewer-->>Writer: Return review feedback
        Writer->>Judge: Submit plan + review feedback
        alt Judge rejects (Needs improvement)
            Judge-->>Writer: Request refinement with feedback
        else Judge approves
            Judge-->>Planner: Sign off on execution plan
        end
        alt Exceeded Cycle Cap (e.g. > 5)
            Writer->>Error: Exceeded cycle limit
            Error-->>Master: Stop execution and report error
        end
    end
    
    Planner-->>Coord: Return signed-off execution plan
    deactivate Planner

    opt Human Approval Required for Plan (Micro Layer)
        Coord->>Human: Present plan & request sign-off
        activate Human
        Note right of Human: Execution suspends for human feedback
        Human-->>Coord: Approve plan or provide feedback / changes
        deactivate Human
        alt Human Rejected Plan
            Coord->>Planner: Loop back to Planner for adjustment
        end
    end

    Note over Coord, Worker: Phase 3: Step-by-Step Task Execution (Micro Gossip Layer)
    loop For each task step in the plan
        Coord->>Worker: Dispatch task step details (YAML task spec)
        activate Worker
        
        Worker->>Research: Request targeted research for step
        Research-->>Worker: Research content & facts
        
        loop Worker Refinement Cycle (Up to NEUROCORE_CYCLE_CAP times)
            Worker->>Worker: Execute task (generate code/content/proofs)
            
            alt Math Task
                Worker->>Verifier: Verify math expressions
                Verifier-->>Worker: Verification report
            end
            
            Worker->>Reviewer: Conduct adversarial review on result
            Reviewer-->>Worker: Review feedback
            
            Worker->>Judge: Submit result + reviews/verifications
            alt Judge Rejects
                Judge-->>Worker: Request refinement with feedback
            else Judge Approves
                Judge-->>Worker: Sign off on task result
            end
            alt Exceeded Cycle Cap (e.g. > 5)
                Worker->>Error: Exceeded cycle limit
                Error-->>Master: Stop execution and report error
            end
        end
        Worker-->>Coord: Return signed-off task results
        deactivate Worker

        opt Human Approval Required for Execution Step
            Coord->>Human: Present step output & request sign-off
            activate Human
            Human-->>Coord: Approve output or provide feedback / changes
            deactivate Human
            alt Human Rejected Step Output
                Coord->>Worker: Loop back to Worker for adjustment
            end
        end
    end

    Note over Coord, End: Phase 4: Completion (Macro Layer)
    Coord->>End: Pass final unified results
    activate End
    End-->>Master: Return results & pass control back
    deactivate End
    deactivate Coord
```

---

## 3. Micro-Routing Transition Specifications

The following transition tables determine the target address for peer-to-peer gossip messaging. When a component completes its stage, it refers to these rules to route the request payload.

### A. Planner Orchestration Sequence
This flow guides the synthesis and approval of execution plans.

```
[Planner] ──> [Researcher] ──> [Writer] ──> [Reviewer] ──> [Judge]
                                 ▲                           │
                                 │       (on_failure)        │
                                 └───────────────────────────┤
                                                             ▼
                                                        (on_success)
                                                             │
                                                             ▼
                                                         [Planner] ──> (Coordinator)
```

| Step | Source Component | Output Port / Target | Target Component | Description / Condition |
| :--- | :--- | :--- | :--- | :--- |
| 1 | **`planner`** | `initiate_research` | **`researcher`** | Dispatches high-level prompt to search engine. |
| 2 | **`researcher`** | `research_completed` | **`writer`** | Forwards search data to start drafting. |
| 3 | **`writer`** | `draft_completed` | **`reviewer`** | Passes draft plan to the adversarial reviewer. |
| 4 | **`reviewer`** | `review_completed` | **`judge`** | Submits draft + critique for sign-off. |
| 5a | **`judge`** | `on_failure` | **`writer`** | Refined needed (loops back to Writer with feedback). |
| 5b | **`judge`** | `on_success` | **`planner`** | Approved (loops back to Planner to format plan). |
| 6 | **`planner`** | `plan_ready` | **`coordinator`** | Delivers validated plan to Coordinator. |

### B. Worker Orchestration Sequence
This flow executes and verifies concrete steps in the plan.

```
[Worker] ──> [Researcher] ──> [Worker (Draft)] ──> [Reviewer] / [Verifier] ──> [Judge]
                                    ▲                                            │
                                    │                (on_failure)                │
                                    └────────────────────────────────────────────┤
                                                                                 ▼
                                                                            (on_success)
                                                                                 │
                                                                                 ▼
                                                                             [Worker] ──> (Coordinator)
```

| Step | Source Component | Output Port / Target | Target Component | Description / Condition |
| :--- | :--- | :--- | :--- | :--- |
| 1 | **`worker`** | `initiate_research` | **`researcher`** | Dispatches specific task prompt for fact-gathering. |
| 2 | **`researcher`** | `research_completed` | **`worker`** | Worker synthesizes research and drafts content. |
| 3 | **`worker`** | `verify_math` | **`verifier`** | *(If math)* Submits math expressions for verification. |
| 4 | **`worker`** / **`verifier`** | `review_needed` | **`reviewer`** | Submits draft + verification reports for critique. |
| 5 | **`reviewer`** | `review_completed` | **`judge`** | Delivers critique and work result to the Judge. |
| 6a | **`judge`** | `on_failure` | **`worker`** | Refinement needed (loops back to rewrite). |
| 6b | **`judge`** | `on_success` | **`worker`** | Approved (loops back to Worker to finalize). |
| 7 | **`worker`** | `task_completed` | **`coordinator`** | Returns completed milestone to Coordinator. |

---

## 4. Gossip Context & State Sharing

To pass information correctly between these stages:
1. **FlowContext Serialization**:
   * The `FlowContext` is passed as a payload envelope in `neurogossip-agent-v3` messages.
   * Important context keys are standard:
     * `task_prompt`: The target instructions.
     * `artifact_path`: Target directory for disk writes (passed dynamically).
     * `research_payload`: Consolidated data from Tavily/Brave/arXiv.
     * `draft_content`: Current work in progress.
     * `review_feedback`: Critique comments.
     * `verification_report`: Automated verification data.
     * `cycle_count`: Track loop iterations to enforce `NEUROCORE_CYCLE_CAP`.
2. **Shared Filesystem**:
   * Heavy content (logs, source codes, draft files) are written directly to the path set in `artifact_path` instead of flooding the context payload, maintaining lightweight messaging.
