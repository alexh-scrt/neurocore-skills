import os
import pytest
import tempfile
import yaml
from flowengine import FlowContext
from neurocore.skills.loader import discover_skills
from neurocore.config.loader import load_config
from neurocore.runtime.executor import load_and_run

def test_skill_discovery():
    # Load default workspace config and check that all our skills are in the registry
    config = load_config(project_root="/home/ubuntu/neurocore-skills")
    registry = discover_skills(config)
    
    expected_skills = [
        "arxiv", "researcher", "planner", "writer", "reviewer",
        "math_verifier", "judge", "fact_checker", "human",
        "start", "end", "error", "coordinator", "worker"
    ]
    
    for s in expected_skills:
        assert s in registry.list_skills(), f"Skill {s} not found in registry"

def test_simple_load_and_run():
    # End-to-end test running the start -> coordinator -> end blueprint
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create a neurocore.yaml
        with open(os.path.join(tmp_dir, "neurocore.yaml"), "w") as f:
            f.write("project:\n  name: test-flow\n")
            
        # Create a blueprint
        bp_yaml = """
name: "test-integration-flow"
version: "1.0"
components:
  - name: flow-start
    type: start
  - name: task-coordinator
    type: coordinator
  - name: flow-end
    type: end
flow:
  type: sequential
  steps:
    - component: flow-start
    - component: task-coordinator
    - component: flow-end
"""
        bp_file = os.path.join(tmp_dir, "flow.yaml")
        with open(bp_file, "w") as f:
            f.write(bp_yaml)
            
        # Run the flow using load_and_run
        # We pass flow_yaml in the initial context to satisfy start and coordinator requirements
        initial_context = {
            "flow_yaml": bp_yaml,
            "arxiv_query": "Attention Is All You Need",
            "research_query": "Transformer models",
            "task_description": "Verify SMT reasoning",
            "writing_prompt": "Draft mathematical summary",
            "content_to_review": "Draft mathematical summary contents",
            "math_expression": "x > 2 and y > 2 => x * y > 4",
            "task_output": "True",
            "quality_criteria": "Must be mathematically verified",
            "claims_to_check": "Transformer models are highly parallelizable",
            "human_prompt": "Approve math proof",
            "task_yaml": "step_id: step_1"
        }
        
        result = load_and_run(
            bp_file,
            project_root="/home/ubuntu/neurocore-skills",
            initial_data=initial_context
        )
        
        # Verify outcomes from each executed stage
        assert result.get("flow_started") is True
        assert result.get("coordinator_status") == "Execution schedule generated successfully"
        assert result.get("flow_completed") is True
