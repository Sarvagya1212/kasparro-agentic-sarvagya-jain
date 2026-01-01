# Skincare Multi-Agent Content Generation System

## Architectural Blueprint: CWD Model

This system implements a **Coordinator-Worker-Delegator (CWD)** architecture with robust safety and verification.

```
┌─────────────────────────────────────────────────────────────────┐
│                      COORDINATOR (Orchestrator)                  │
│                   Role: "Strategic Director"                     │
│   - Guardrails integration (before_model_callback)              │
│   - High-level routing decisions                                │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
        ┌──────────┐   ┌──────────────┐   ┌──────────┐
        │DataAgent │   │  DELEGATOR   │   │Generation│
        │          │   │ (Proj. Mgr)  │   │  Agent   │
        └──────────┘   └──────────────┘   └──────────┘
              │               │                 │
              ▼               ▼                 ▼
        ┌──────────┐   ┌─────────────┐   ┌──────────┐
        │Synthetic │   │  WORKERS    │   │ VERIFIER │
        │DataAgent │   │ +Validation │   │  Agent   │
        └──────────┘   │  (RETRY ↺)  │   └──────────┘
                       └─────────────┘
```

## Key Architecture Features

| Feature | Implementation | Location |
|---------|----------------|----------|
| **CWD Model** | Coordinator → Delegator → Workers | `orchestrator.py`, `delegator.py`, `workers.py` |
| **Role Engineering** | `role`, `backstory`, `system_prompt` | `agents.py` |
| **Instruction Hierarchy** | `validate_instruction()` | `agents.py:20-38` |
| **Input Guardrails** | `before_model_callback()` | `guardrails.py` |
| **Tool Guardrails** | `before_tool_callback()` | `guardrails.py` |
| **HITL Gate** | `HITLGate.request_authorization()` | `hitl.py` |
| **Independent Verifier** | `VerifierAgent` | `verifier.py` |
| **Loop-Back** | `ValidationWorker` → RETRY | `delegator.py` |

## Safety Infrastructure

### Guardrails (`guardrails.py`)
- **Input validation**: Blocks jailbreaks, PII
- **Tool validation**: Checks required params, constraints

### HITL (`hitl.py`)
- **High-stakes actions**: `write_output_file`, `publish_content`
- **Auto-approve mode**: For testing
- **Authorization log**: Full audit trail

### VerifierAgent (`verifier.py`)
- **Independent from ValidationWorker**
- **Checks**: Content accuracy, harmful patterns, schema compliance

## Agent Personas

| Agent | Role | Backstory |
|-------|------|-----------|
| Coordinator | Strategic Director | Ensures system integrity |
| Delegator | Project Manager | Balances speed with quality |
| BenefitsWorker | Benefits Specialist | Dermatologist assistant |
| QuestionsWorker | FAQ Generator | Customer success specialist |
| ValidationWorker | QA Officer | Strict auditor |
| VerifierAgent | Independent Auditor | Never trusts, always verifies |

## Folder Structure

```
skincare_agent_system/
├── orchestrator.py      # Coordinator
├── delegator.py         # Delegator with retry loop
├── workers.py           # Specialized workers
├── verifier.py          # Independent verifier
├── guardrails.py        # Safety callbacks
├── hitl.py              # Human-in-the-Loop
├── agents.py            # BaseAgent with roles
├── models.py            # Pydantic models, TaskDirective
├── agent_implementations.py  # DataAgent, etc.
├── tools/               # ToolRegistry
├── logic_blocks/        # FAQ, Benefits logic
├── templates/           # JSON templates
├── data/                # Product data
└── main.py              # Entry point
```

## Run Commands

```bash
# Main execution
python -m skincare_agent_system.main

# Tests
pytest tests/ -v
pytest tests/test_safety.py -v
pytest tests/test_roles.py -v
```
