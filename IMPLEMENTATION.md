# Implementation Summary

## Architecture: Blackboard Pattern

```
┌─────────────────────────────────────────────────────────────┐
│                    GLOBAL CONTEXT                            │
│  (Blackboard - Single Source of Truth)                      │
│  product_input → generated_content → errors → stage         │
└──────────────────────────┬──────────────────────────────────┘
                           │
            ┌──────────────▼──────────────┐
            │      PRIORITY ROUTER         │
            │   can_handle(state) → bool   │
            └──────────────┬──────────────┘
                           │
    ┌──────────┬───────────┼───────────┬──────────┐
    ▼          ▼           ▼           ▼          ▼
  INGEST → SYNTHESIS → DRAFTING → VERIFICATION → COMPLETE
  (Usage)  (Questions) (Compare)  (Validate)     (Done)
```

---

## Core Components

| Component | File | Description |
|-----------|------|-------------|
| **GlobalContext** | `core/models.py` | Pydantic shared state with ProcessingStage |
| **PriorityRouter** | `core/proposals.py` | Simple `can_handle()` boolean routing |
| **Orchestrator** | `core/orchestrator.py` | Stage-based loop with Reflexion |
| **EventBus** | `core/event_bus.py` | Observer pattern, non-blocking |
| **Workers** | `actors/workers.py` | Stage-specific agents |
| **Providers** | `infrastructure/providers.py` | LLM abstraction + CircuitBreaker |

---

## Key Patterns

### 1. Stage-Based Routing

```python
class UsageWorker:
    def can_handle(self, state: GlobalContext) -> bool:
        return state.stage == ProcessingStage.INGEST
```

### 2. Reflexion Self-Correction

```python
if result.status == VALIDATION_FAILED:
    context.set_reflexion("Need 3 more questions")
    context.stage = ProcessingStage.SYNTHESIS  # Retry
```

### 3. CircuitBreaker Pattern

```python
class CircuitBreaker:
    failure_threshold = 3  # Opens after 3 failures
    # Auto-switches MistralProvider → OfflineRuleProvider
```

### 4. Observer EventBus

```python
EventBus.emit(Events.AGENT_COMPLETE, {"agent": "QuestionsWorker"})
# Non-blocking async notification to all subscribers
```

---

## Processing Flow

| Step | Stage | Worker | Output |
|------|-------|--------|--------|
| 1 | INGEST | UsageWorker | Extract usage instructions |
| 2 | SYNTHESIS | QuestionsWorker | Generate 20 FAQ questions |
| 3 | DRAFTING | ComparisonWorker | Compare products |
| 4 | VERIFICATION | ValidationWorker | Validate ≥15 FAQs |
| 5 | COMPLETE | - | Generate output JSON |

---

## Provider Abstraction

```
IIntelligenceProvider (ABC)
    ├── MistralProvider     # API + retries + backoff
    └── OfflineRuleProvider # Dynamic regex/template (no static mocks)
            │
            └── CircuitBreakerWrapper (auto-switch on failure)
```

---

## Configuration

| Source | Path | Purpose |
|--------|------|---------|
| Product Data | `config/run_config.json` | External injection |
| Environment | `MISTRAL_API_KEY` | LLM provider selection |
| Environment | `RUN_CONFIG` | Custom config path |

---

## Run Commands

```bash
# Run system
python run_agent.py

# Test
pytest

# With different config
RUN_CONFIG=custom.json python run_agent.py
```

---

## Output Files

| File | Content |
|------|---------|
| `output/faq.json` | 20 categorized Q&A pairs |
| `output/product_page.json` | Product details |
| `output/comparison_page.json` | Product comparison |
