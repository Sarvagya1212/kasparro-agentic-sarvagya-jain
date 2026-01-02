import os
import sys
from pathlib import Path

# Load environment variables from .env file
from dotenv import load_dotenv

load_dotenv()

import logging

from skincare_agent_system.actors.agent_implementations import (
    DataAgent,
    GenerationAgent,
    SyntheticDataAgent,
)
from skincare_agent_system.actors.delegator import DelegatorAgent
from skincare_agent_system.actors.verifier import VerifierAgent
from skincare_agent_system.core.orchestrator import Orchestrator
from skincare_agent_system.security.hitl import get_hitl_gate

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Check if LLM is enabled
LLM_ENABLED = os.getenv("MISTRAL_API_KEY") is not None


def main():
    """
    Main entry point for the Agentic Skincare System (CWD Architecture).
    Now includes VerifierAgent for independent verification.
    """
    print("\n" + "=" * 70)
    print("SKINCARE MULTI-AGENT CWD SYSTEM (with Safety & Verification)")
    print("=" * 70)
    print("Initializing Agents...")

    # Show LLM status
    if LLM_ENABLED:
        print("🧠 LLM Mode: ENABLED (Mistral 7B)")
    else:
        print("⚡ LLM Mode: DISABLED (using heuristics)")

    # Initialize HITL gate (auto_approve=True for non-interactive demo)
    hitl_gate = get_hitl_gate(auto_approve=True)

    # Setup security subsystems
    from skincare_agent_system.infrastructure.agent_monitor import (
        AnomalyThresholds,
        configure_monitor,
    )
    from skincare_agent_system.security.credential_shim import (
        VaultBackend,
        configure_shim,
    )

    # Configure shim with identity verification
    configure_shim(enable_identity_verification=True)

    # Configure monitor with auto-revocation
    configure_monitor(
        thresholds=AnomalyThresholds(max_tokens_per_hour=100000),
        enable_auto_revoke=True,
    )

    import logging

    logging.getLogger("main").info("Security subsystems initialized (Shim + Monitor)")

    # 1. Initialize Coordinator (Orchestrator)
    coordinator = Orchestrator()

    # 2. Register Agents
    coordinator.register_agent(DataAgent("DataAgent"))
    coordinator.register_agent(SyntheticDataAgent("SyntheticDataAgent"))
    # Analysis and Validation are now handled by Delegator
    coordinator.register_agent(DelegatorAgent("DelegatorAgent"))
    coordinator.register_agent(GenerationAgent("GenerationAgent"))
    # Independent Verifier (separate from ValidationWorker)
    coordinator.register_agent(VerifierAgent("VerifierAgent"))

    print("\nStarting Autonomous Workflow (LangGraph Enabled)...")
    print("-" * 30)

    # 3. Create and Run Graph
    try:
        from skincare_agent_system.core.workflow_graph import create_workflow_graph

        # Map agents for the graph
        agents_map = {
            "DataAgent": coordinator.agents["DataAgent"],
            "SyntheticDataAgent": coordinator.agents["SyntheticDataAgent"],
            "DelegatorAgent": coordinator.agents["DelegatorAgent"],
            "GenerationAgent": coordinator.agents["GenerationAgent"],
            "VerifierAgent": coordinator.agents["VerifierAgent"],
        }

        app = create_workflow_graph(coordinator, agents_map)

        # Initial state
        initial_state = {
            "context": coordinator.context,
            "next_agent": None,
            "messages": [],
            "steps_count": 0,
            "workflow_status": "active",
        }

        # Invoke graph
        final_state = app.invoke(initial_state)
        final_context = final_state["context"]

    except ImportError:
        print("⚠️ LangGraph not installed. Falling back to legacy orchestrator.")
        final_context = coordinator.run()

    print("\n" + "=" * 70)
    print("WORKFLOW FINISHED")
    print("=" * 70)

    if coordinator.state.value == "COMPLETED" or final_context.is_valid:
        print("✅ Success! All artifacts generated and verified.")
        print(f"Stats: {len(final_context.execution_history)} steps executed.")
        print("Execution Trace:")
        for step in final_context.execution_history:
            print(f" -> {step}")

        print("\nDecision Log (Traceability Proven):")
        for entry in final_context.decision_log[-10:]:  # Last 10 entries
            print(f"[{entry['timestamp']}] {entry['agent']}: {entry['reason']}")

        # Show HITL log if any
        hitl_log = hitl_gate.get_authorization_log()
        if hitl_log:
            print("\nHITL Authorization Log:")
            for entry in hitl_log:
                print(f"  [{entry['status']}] {entry['action']}")
    else:
        print("❌ Workflow failed or incomplete.")
        print(f"State: {coordinator.state.value}")
        print(f"Errors: {final_context.validation_errors}")


if __name__ == "__main__":
    main()
