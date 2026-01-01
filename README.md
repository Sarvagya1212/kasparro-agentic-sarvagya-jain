# Kasparro AI - Multi-Agent Content Generation System

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **Applied AI Engineer Assignment** - Multi-Agent Content Generation System

## 🎯 What This System Does

Transforms product data → Structured JSON content pages through a **truly agentic** system where **agents propose actions** and the Coordinator selects the best proposal.

**Input:** GlowBoost Vitamin C Serum product data
**Output:** 3 JSON files (FAQ, Product Page, Comparison)

## ✨ Key Features

| Feature | Implementation |
|---------|----------------|
| **Agent Proposals** | Agents assess context and propose actions |
| **Dynamic Selection** | Coordinator picks highest-confidence proposal |
| **Event-Driven** | Agents communicate via EventBus |
| **CWD Architecture** | Coordinator → Delegator → Workers |
| **Role Engineering** | Agent personas with backstories |
| **Safety & Verification** | Guardrails, HITL, VerifierAgent |
| **Memory System** | Working, Episodic, Knowledge Base |
| **State Management** | StateSpace with transitions |

## 🤖 True Agent Autonomy

```
BEFORE (Deterministic):
  Coordinator decides: "Run DataAgent next"

AFTER (Agent-Driven):
  DataAgent proposes: "I can load data (0.95 confidence)"
  Coordinator selects: Best proposal wins
```

### Decision Log Example:
```
[Coordinator] Collected 5 proposals from agents
  → DataAgent: load_data (0.95) - No product data loaded
  → SyntheticAgent: generate (0.0) - Need data first
  → DelegatorAgent: delegate (0.0) - Need data first
[Coordinator] SELECTED: DataAgent (0.95) - I can fetch and validate data
```

## 🚀 Quick Start

```bash
# Clone and run
git clone https://github.com/Sarvagya1212/kasparro-agentic-sarvagya-jain.git
cd kasparro-agentic-sarvagya-jain
python -m skincare_agent_system.main

# Run tests
pytest tests/ -v
```

## 📊 Architecture

```
┌─────────────────────────────────────────┐
│           COORDINATOR                   │
│  (Collects proposals, selects best)    │
└─────────────────────────────────────────┘
              │ Proposals
    ┌─────────┼─────────┐
    ▼         ▼         ▼
┌────────┐ ┌─────────┐ ┌──────────┐
│  Data  │ │Delegator│ │Generation│
│ Agents │ │+Workers │ │ +Verify  │
└────────┘ └─────────┘ └──────────┘
   Each agent: can_handle() + propose()
```

## 📁 Project Structure

```
skincare_agent_system/
├── orchestrator.py    # Coordinator (proposal-based)
├── proposals.py       # ProposalSystem, EventBus, Goals
├── delegator.py       # Delegator with proposals
├── workers.py         # Specialized Workers
├── verifier.py        # Independent Verifier
├── agents.py          # BaseAgent with can_handle/propose
├── guardrails.py      # Safety Callbacks
├── hitl.py            # Human-in-the-Loop
├── state_manager.py   # State Space
├── memory.py          # Memory System
├── evaluation.py      # Failure Analysis
├── tracer.py          # Execution Tracing
└── tools/             # Role-based tool access
```

## 🧪 Testing

```bash
pytest tests/ -v
pytest tests/test_proposals.py -v  # Agent autonomy tests
pytest tests/test_safety.py -v
pytest tests/test_memory.py -v
pytest tests/test_tools.py -v
```

## 👤 Author

**Sarvagya Jain**
Applied AI Engineer Assignment - Kasparro
