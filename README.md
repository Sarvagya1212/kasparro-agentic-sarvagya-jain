# Skincare Agent System (SAS)

**Autonomous multi-agent system for skincare content generation using Blackboard architecture.**

---

## 🚀 Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the system
python run_agent.py
```

**Output:** 3 JSON files in `output/` (faq.json, product_page.json, comparison_page.json)

---

## 🏗️ Architecture

### Blackboard Pattern with Stage-Based Routing

```
┌─────────────────────────────────────────────────────────────┐
│                    GLOBAL CONTEXT                            │
│  (Blackboard - Single Source of Truth)                      │
│  • product_input • generated_content • errors • stage       │
└──────────────────────────────────┬──────────────────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │     PRIORITY ROUTER          │
                    │  can_handle(state) → bool   │
                    └──────────────┬──────────────┘
                                   │
    ┌──────────────────────────────┼──────────────────────────────┐
    │              │               │               │              │
    ▼              ▼               ▼               ▼              ▼
┌────────┐   ┌─────────────┐  ┌────────────┐  ┌────────────┐  ┌──────────┐
│ INGEST │ → │ SYNTHESIS   │→ │ DRAFTING   │→ │VERIFICATION│→ │ COMPLETE │
│ Usage  │   │ Questions   │  │ Comparison │  │ Validation │  │  Done    │
└────────┘   └─────────────┘  └────────────┘  └────────────┘  └──────────┘
```

### Key Components

| Component | File | Purpose |
|-----------|------|---------|
| **GlobalContext** | `core/models.py` | Pydantic model - shared state |
| **PriorityRouter** | `core/proposals.py` | Simple `can_handle()` routing |
| **Orchestrator** | `core/orchestrator.py` | Stage-based execution loop |
| **Workers** | `actors/workers.py` | Stage-specific agents |
| **EventBus** | `core/event_bus.py` | Observer pattern logging |
| **Providers** | `infrastructure/providers.py` | LLM abstraction |

---

## 🔄 Processing Stages

| Stage | Worker | Action |
|-------|--------|--------|
| INGEST | UsageWorker | Extract usage instructions |
| SYNTHESIS | QuestionsWorker | Generate 20 FAQ questions |
| DRAFTING | ComparisonWorker | Compare products |
| VERIFICATION | ValidationWorker | Validate 15+ FAQs |
| COMPLETE | - | Workflow done |

---

## ⚡ Features

### 1. Intelligence Provider Abstraction
```python
from infrastructure.providers import get_provider

provider = get_provider()  # Auto-selects Mistral or Offline
questions = provider.generate_faq(product_data)
```

- **MistralProvider**: API with retries + exponential backoff
- **OfflineRuleProvider**: Dynamic regex/template generation (no static mocks)
- **CircuitBreaker**: Auto-switches after 3 failures

### 2. Reflexion Self-Correction
On validation failure (< 15 FAQs):
1. Orchestrator sets `context.reflexion_feedback`
2. Prompt: "Generated X questions. Need Y more."
3. QuestionsWorker retries with amended context

### 3. JSON Structured Logging
```json
{"timestamp": "...", "agent": "QuestionsWorker", "level": "INFO", "action": "Generated 20 questions", "trace_id": "abc-123"}
```

### 4. Configuration Injection
```bash
# Product data in external config (no hardcoding)
config/run_config.json

# Override with env variable
RUN_CONFIG=custom_config.json python run_agent.py
```

---

## 📁 Project Structure

```
kasparro-content-generation/
├── run_agent.py              # Main entry point
├── config/
│   └── run_config.json       # Product data config
├── skincare_agent_system/
│   ├── core/
│   │   ├── models.py         # GlobalContext, ProcessingStage
│   │   ├── proposals.py      # PriorityRouter (can_handle)
│   │   ├── orchestrator.py   # Stage-based orchestration
│   │   ├── event_bus.py      # Observer pattern
│   │   └── validators.py     # Schema validation
│   ├── actors/
│   │   └── workers.py        # UsageWorker, QuestionsWorker, etc.
│   ├── infrastructure/
│   │   └── providers.py      # IIntelligenceProvider
│   ├── logic_blocks/
│   │   ├── question_generator.py
│   │   ├── comparison_block.py
│   │   └── usage_block.py
│   └── templates/
└── output/                   # Generated JSON files
```

---

## 🧪 Testing

```bash
pytest                           # Run all tests
pytest --cov=skincare_agent_system  # With coverage
```

---

## 🔧 Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `MISTRAL_API_KEY` | API key for Mistral LLM | None (uses OfflineRuleProvider) |
| `RUN_CONFIG` | Path to product config | `config/run_config.json` |

---

## 📊 Output Example

**faq.json** (20 Q&As):
```json
{
  "product": "GlowBoost Vitamin C Serum",
  "total_questions": 20,
  "categories": ["Informational", "Usage", "Safety", "Purchase", "Results"]
}
```

---

## 📜 License

MIT License
