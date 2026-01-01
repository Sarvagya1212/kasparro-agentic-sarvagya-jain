# Kasparro AI - Multi-Agent Content Generation System

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **Applied AI Engineer Assignment** - Multi-Agent Content Generation System

## 🎯 What This System Does

Transforms product data → Structured JSON content pages through a **Coordinator-Worker-Delegator (CWD)** architecture with safety, memory, and observability.

**Input:** GlowBoost Vitamin C Serum product data
**Output:** 3 JSON files (FAQ, Product Page, Comparison)

## ✨ Key Features

| Feature | Implementation |
|---------|----------------|
| **CWD Architecture** | Coordinator → Delegator → Workers |
| **Role Engineering** | Agent personas with backstories |
| **Safety & Verification** | Guardrails, HITL, VerifierAgent |
| **Memory System** | Working, Episodic, Knowledge Base |
| **State Management** | StateSpace with transitions |
| **Evaluation & Observability** | Failure taxonomy, execution tracing |

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
│    (State + Memory + Tracing)          │
└─────────────────────────────────────────┘
              │
    ┌─────────┼─────────┐
    ▼         ▼         ▼
┌────────┐ ┌─────────┐ ┌──────────┐
│  Data  │ │Delegator│ │Generation│
│ Agents │ │+Workers │ │ +Verify  │
└────────┘ └─────────┘ └──────────┘
```

## 📁 Project Structure

```
skincare_agent_system/
├── orchestrator.py    # Coordinator
├── delegator.py       # Delegator
├── workers.py         # Specialized Workers
├── verifier.py        # Independent Verifier
├── guardrails.py      # Safety Callbacks
├── hitl.py            # Human-in-the-Loop
├── state_manager.py   # State Space
├── memory.py          # Memory System
├── evaluation.py      # Failure Analysis
├── tracer.py          # Execution Tracing
└── ...
```

## 🧪 Testing

```bash
pytest tests/ -v
pytest tests/test_safety.py -v
pytest tests/test_memory.py -v
pytest tests/test_evaluation.py -v
```

## 👤 Author

**Sarvagya Jain**
Applied AI Engineer Assignment - Kasparro
