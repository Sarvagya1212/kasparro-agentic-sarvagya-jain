# Skincare Agent System Package

This package contains the core implementation of the Multi-Agent Content Generation System.

## Module Overview

### Core Agent Logic
*   **`agents.py`**: Base class definition with `ReAct` reasoning and `SelfReflections` capabilities.
*   **`orchestrator.py`**: The central nervous system. Uses a `ProposalSystem` to dynamically select agents based on context.
*   **`delegator.py`**: The Analysis Phase manager. Uses **HTN (Hierarchical Task Network)** planning to decompose goals into worker tasks.
*   **`workers.py`**: Domain specialists (`Benefits`, `Usage`, `Questions`) that perform actual content extraction.

### Intelligence & Autonomy
*   **`proposals.py`**: Implements the `AgentProposal` protocol and `EventBus` for decentralized coordination.
*   **`reasoning.py`**: Contains `TaskDecomposer` (HTN), `ReActReasoner`, and `TreeOfThoughts` algorithms.
*   **`reflection.py`**: Provides self-critique mechanisms for agents to improve their own outputs.

### Security & Safety
*   **`guardrails.py`**: Input validation and PII detection.
*   **`emergency_controls.py`**: Circuit breakers and panic buttons for system stability.
*   **`credential_shim.py`**: Securely manages potential API keys (even if mocked/not used).

### Content Generation
*   **`templates/`**: Jinja2-style templates for `faq`, `product_page`, and `comparison`.
*   **`logic_blocks/`**: Reusable extraction algorithms (e.g., ingredient cross-referencing).

## Usage

This package is designed to be run as a module:

```bash
python -m skincare_agent_system.main
```

Or imported for custom workflows:

```python
from skincare_agent_system.core.orchestrator import Orchestrator
from skincare_agent_system.proposals import ProposalSystem

# Custom bootstrapping
system = ProposalSystem()
orch = Orchestrator(proposal_system=system)
orch.run()
```
