# Kasparro AI - Multi-Agent Content Generation System

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **Applied AI Engineer Assignment** - Multi-Agent Content Generation System

## 🎯 What This System Does

Transforms product data → Structured JSON content pages through a **Coordinator-Worker-Delegator (CWD)** architecture with safety guardrails.

**Input:** GlowBoost Vitamin C Serum product data
**Output:** 3 JSON files (FAQ, Product Page, Comparison)
**Method:** CWD orchestration + Role Engineering + Safety Verification

## ✨ Key Features

| Feature | Implementation |
|---------|----------------|
| **CWD Architecture** | Coordinator → Delegator → Specialized Workers |
| **Role Engineering** | Agents have personas (role/backstory) |
| **Instruction Hierarchy** | SYSTEM > USER priority enforcement |
| **Guardrails** | Input/tool validation callbacks |
| **HITL Gate** | Human-in-the-Loop for high-stakes actions |
| **VerifierAgent** | Independent post-generation auditor |
| **Loop-Back Mechanism** | ValidationWorker triggers RETRY |
| **15+ FAQ Questions** | Validated by `ValidationWorker.MIN_FAQ_QUESTIONS` |

## 🚀 Quick Start

```bash
# Clone repository
git clone https://github.com/Sarvagya1212/kasparro-agentic-sarvagya-jain.git
cd kasparro-agentic-sarvagya-jain

# Run the agentic pipeline
python -m skincare_agent_system.main

# Run all tests
pytest tests/ -v
```

**Output:**
```
✅ Success! All artifacts generated and verified.
→ output/faq.json (15 questions)
→ output/product_page.json
→ output/comparison_page.json
```

## 📊 System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      COORDINATOR (Orchestrator)                  │
│                   Role: Strategic Director                       │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
  ┌──────────┐         ┌──────────────┐       ┌──────────┐
  │DataAgent │         │  DELEGATOR   │       │Generation│
  │          │────────▶│(Project Mgr) │──────▶│  Agent   │
  └──────────┘         └──────────────┘       └──────────┘
        │                     │                     │
        ▼                     ▼                     ▼
  ┌──────────────┐     ┌─────────────────┐   ┌──────────┐
  │SyntheticData │     │    WORKERS      │   │ VERIFIER │
  │   Agent      │     │ ├─Benefits      │   │   Agent  │
  └──────────────┘     │ ├─Usage         │   └──────────┘
                       │ ├─Questions     │        ▲
                       │ ├─Comparison    │        │
                       │ └─Validation    │   Independent
                       └─────────────────┘     Auditor
```

## 🛡️ Safety Features

| Component | Purpose | Location |
|-----------|---------|----------|
| **Guardrails** | Input/tool validation | `guardrails.py` |
| **HITL Gate** | Human authorization | `hitl.py` |
| **VerifierAgent** | Independent verification | `verifier.py` |

## 📁 Project Structure

```
kasparro-content-generation/
├── skincare_agent_system/
│   ├── main.py              # Entry point
│   ├── orchestrator.py      # Coordinator
│   ├── delegator.py         # Delegator
│   ├── workers.py           # Specialized Workers
│   ├── verifier.py          # Independent Verifier
│   ├── guardrails.py        # Safety callbacks
│   ├── hitl.py              # Human-in-the-Loop
│   ├── models.py            # Pydantic models
│   ├── agents.py            # BaseAgent with roles
│   ├── tools/               # ToolRegistry
│   ├── logic_blocks/        # FAQ, Benefits logic
│   ├── templates/           # JSON templates
│   └── data/                # Product data
├── output/                  # Generated JSON
└── tests/
    ├── test_roles.py        # Role/hierarchy tests
    ├── test_safety.py       # Safety tests
    └── test_pipeline.py     # Integration tests
```

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Test safety features
pytest tests/test_safety.py -v

# Test role engineering
pytest tests/test_roles.py -v
```

## ✅ Assignment Compliance

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Multi-agent system | ✅ | CWD with 8+ agents |
| Custom templates | ✅ | 3 template classes |
| Reusable logic blocks | ✅ | 4 tool modules |
| 15+ questions | ✅ | Validated by worker |
| 3 JSON outputs | ✅ | faq, product, comparison |
| Safety verification | ✅ | VerifierAgent + Guardrails |
| Role-based agents | ✅ | Personas + hierarchy |

## 👤 Author

**Sarvagya Jain**
Applied AI Engineer Assignment - Kasparro
