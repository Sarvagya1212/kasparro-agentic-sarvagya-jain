import sys
from pathlib import Path

from .agent_implementations import DataAgent, GenerationAgent, SyntheticDataAgent
from .delegator import DelegatorAgent
from .hitl import get_hitl_gate
from .orchestrator import Orchestrator
from .verifier import VerifierAgent


def main():
    """
    Main entry point for the Agentic Skincare System (CWD Architecture).
    Now includes VerifierAgent for independent verification.
    """
    print("\n" + "=" * 70)
    print("SKINCARE MULTI-AGENT CWD SYSTEM (with Safety & Verification)")
    print("=" * 70)
    print("Initializing Agents...")

    # Initialize HITL gate (auto_approve=True for non-interactive demo)
    hitl_gate = get_hitl_gate(auto_approve=True)

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

    print("\nStarting Autonomous Workflow...")
    print("-" * 30)

    # 3. Run the System
    final_context = coordinator.run()

    print("\n" + "=" * 70)
    print("WORKFLOW FINISHED")
    print("=" * 70)

    if coordinator.state.value == "COMPLETED":
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
