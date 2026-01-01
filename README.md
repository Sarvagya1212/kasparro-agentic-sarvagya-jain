# Kasparro AI - Multi-Agent Content Generation System

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-142%20passing-green.svg)]()

> **Applied AI Engineer Assignment** - Production-Ready Agentic System

## 🎯 What This Does

Transforms product data → Structured JSON content pages through a **truly agentic** system following production best practices.

## ✨ Production Best Practices

| Practice | Implementation |
|----------|----------------|
| **CWD Architecture** | Coordinator → Delegator → Workers |
| **Agent Proposals** | Agents propose actions, best selected |
| **Human-in-the-Loop** | HITLGate for high-stakes actions |
| **Guardrails** | Input validation, tool callbacks |
| **Least Privilege** | ActionValidator per-agent scopes |
| **Failure Taxonomy** | 5-category failure analysis |
| **142 Tests** | Full offline evaluation |

## 🛡️ Security Layers

```
Input → InjectionDefense → Guardrails → ActionValidator
      → RoleChecker → HITLGate → Tool Execution
      → InterAgentAuditor → VerifierAgent → Output
```

## 🚀 Quick Start

```bash
git clone https://github.com/Sarvagya1212/kasparro-agentic-sarvagya-jain.git
cd kasparro-agentic-sarvagya-jain
python -m skincare_agent_system.main
pytest tests/ -v
```

## 📁 Key Files

| File | Purpose |
|------|---------|
| `orchestrator.py` | Coordinator with ProposalSystem |
| `proposals.py` | Agent autonomy, EventBus, Goals |
| `delegator.py` | Task distribution to Workers |
| `guardrails.py` | InjectionDefense, safety hooks |
| `action_validator.py` | Hallucination prevention |
| `failure_detector.py` | Role compliance, handoff audit |
| `hitl.py` | Human-in-the-Loop gate |
| `reasoning.py` | CoT, ReAct, HTN decomposition |
| `reflection.py` | Agent self-critique |
| `memory.py` | Working, Episodic, SessionState |

## 🧪 Testing

```bash
pytest tests/ -v                    # All 142 tests
pytest tests/test_security.py -v    # Security (23 tests)
pytest tests/test_proposals.py -v   # Autonomy (17 tests)
pytest tests/test_reasoning.py -v   # Reasoning (19 tests)
```

## 👤 Author

**Sarvagya Jain** - Applied AI Engineer Assignment
