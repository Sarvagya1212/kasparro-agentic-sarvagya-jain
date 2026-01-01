# Multi-Agent Content Generation System

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-142%20passing-green.svg)]()
[![CI](https://img.shields.io/badge/CI-passing-brightgreen.svg)]()

> **Kasparro Applied AI Engineer Assignment** — A modular agentic automation system that transforms product data into structured, machine-readable content pages.

---

## 🎯 Assignment Requirements ✅

| Requirement | Status | Implementation |
|-------------|--------|----------------|
| Parse & understand product data | ✅ | `ProductData` Pydantic model |
| Generate 15+ categorized questions | ✅ | `QuestionsWorker` (5 categories) |
| FAQ Template | ✅ | `templates/faq_template.py` |
| Product Description Template | ✅ | `templates/product_page_template.py` |
| Comparison Template | ✅ | `templates/comparison_template.py` |
| Reusable content logic blocks | ✅ | `logic_blocks/` (4 blocks) |
| FAQ Page JSON | ✅ | `output/faq.json` |
| Product Page JSON | ✅ | `output/product_page.json` |
| Comparison Page JSON | ✅ | `output/comparison_page.json` |
| Pipeline runs via agents | ✅ | CWD architecture |
| Clear agent boundaries | ✅ | Single responsibility per agent |
| Orchestration graph | ✅ | ProposalSystem + EventBus |

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      COORDINATOR                            │
│   Orchestrator with ProposalSystem (Dynamic Agent Selection)│
└─────────────────────────────┬───────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
    ┌───────────┐      ┌───────────┐      ┌───────────┐
    │ DataAgent │      │ Delegator │      │ Generator │
    │ + Synth   │      │ (Manager) │      │ + Verifier│
    └───────────┘      └─────┬─────┘      └───────────┘
                             │
               ┌─────────────┼─────────────┐
               ▼             ▼             ▼
         ┌──────────┐ ┌───────────┐ ┌────────────┐
         │ Benefits │ │  Usage    │ │ Questions  │
         │  Worker  │ │  Worker   │ │   Worker   │
         └──────────┘ └───────────┘ └────────────┘
```

**Pattern:** Coordinator-Worker-Delegator (CWD) Model

---

## 📁 Project Structure

```
skincare_agent_system/
├── main.py                 # Entry point
├── orchestrator.py         # Coordinator with ProposalSystem
├── delegator.py            # Task distribution manager
├── workers.py              # Specialized workers (Benefits, Usage, Questions)
├── agents.py               # BaseAgent with autonomy support
├── agent_implementations.py # DataAgent, GenerationAgent, etc.
├── verifier.py             # Independent output verification
│
├── templates/              # Template Engine
│   ├── faq_template.py
│   ├── product_page_template.py
│   └── comparison_template.py
│
├── logic_blocks/           # Reusable Content Logic
│   ├── benefits_block.py
│   ├── usage_block.py
│   ├── comparison_block.py
│   └── question_generator.py
│
├── proposals.py            # Agent proposals, EventBus, GoalManager
├── reasoning.py            # CoT, ReAct, HTN decomposition
├── reflection.py           # Agent self-critique
├── memory.py               # Working, Episodic, Knowledge Base
├── guardrails.py           # Input validation, InjectionDefense
├── action_validator.py     # Action scope validation
├── failure_detector.py     # Role compliance, handoff audit
├── hitl.py                 # Human-in-the-Loop authorization
├── state_manager.py        # Workflow state tracking
├── evaluation.py           # Failure analysis, metrics
└── tracer.py               # Logging and tracing

output/
├── faq.json                # Generated FAQ page
├── product_page.json       # Generated product description
└── comparison_page.json    # Generated comparison (GlowBoost vs Product B)

tests/                      # 142 tests
docs/
└── projectdocumentation.md # System design documentation
```

---

## 🚀 Quick Start

```bash
# Clone repository
git clone https://github.com/Sarvagya1212/kasparro-agentic-sarvagya-jain.git
cd kasparro-agentic-sarvagya-jain

# Install dependencies
pip install -r requirements.txt

# Run the system
python -m skincare_agent_system.main

# Run tests
pytest tests/ -v
```

---

## � Agent Workflow

1. **DataAgent** → Parses product data into `ProductData` model
2. **SyntheticDataAgent** → Creates fictional Product B for comparison
3. **DelegatorAgent** → Delegates to specialized workers:
   - BenefitsWorker → Extracts benefits
   - UsageWorker → Formats usage instructions
   - QuestionsWorker → Generates 15+ categorized questions
4. **ValidationAgent** → Validates analysis results
5. **GenerationAgent** → Renders templates to JSON
6. **VerifierAgent** → Verifies output correctness

**Dynamic Selection:** Agents propose actions with confidence scores. Orchestrator selects the best proposal each iteration.

---

## 🛡️ Safety & Guardrails

| Layer | Purpose |
|-------|---------|
| `InjectionDefense` | Blocks 12+ prompt injection patterns |
| `Guardrails` | Input validation, PII detection |
| `ActionValidator` | Per-agent action scope enforcement |
| `RoleComplianceChecker` | Prevents agents exceeding boundaries |
| `HITLGate` | Human approval for high-stakes actions |
| `InterAgentAuditor` | Verifies inter-agent handoffs |
| `VerifierAgent` | Independent output verification |

---

## 🧪 Testing

```bash
pytest tests/ -v                    # All 142 tests
pytest tests/test_pipeline.py -v    # End-to-end (8 tests)
pytest tests/test_proposals.py -v   # Autonomy (17 tests)
pytest tests/test_security.py -v    # Security (23 tests)
pytest tests/test_templates.py -v   # Templates (12 tests)
pytest tests/test_logic_blocks.py -v # Content blocks (15 tests)
```

---

## 📄 Output Examples

### FAQ Page (`output/faq.json`)
```json
{
  "page_type": "faq",
  "product_name": "GlowBoost Vitamin C Serum",
  "questions": [
    {
      "category": "Informational",
      "question": "What is GlowBoost Vitamin C Serum?",
      "answer": "A brightening serum with 10% Vitamin C..."
    }
  ]
}
```

### Comparison Page (`output/comparison_page.json`)
```json
{
  "page_type": "comparison",
  "product_a": { "name": "GlowBoost Vitamin C Serum", ... },
  "product_b": { "name": "RadiantGlow Niacinamide Serum", ... },
  "comparison_points": [ ... ]
}
```

---

## 📚 Documentation

- `docs/projectdocumentation.md` — Problem statement, solution overview, system design
- `IMPLEMENTATION.md` — Architecture diagrams, security layers
- `project_description.md` — Detailed file-by-file documentation

---

## 👤 Author

**Sarvagya Jain**  
Applied AI Engineer Assignment — Kasparro
