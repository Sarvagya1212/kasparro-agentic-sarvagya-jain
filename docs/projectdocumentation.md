# Project Documentation: Skincare Agent System

## Executive Summary

The Skincare Agent System (SAS) is an autonomous multi-agent framework for skincare content generation using **Blackboard Architecture** with stage-based routing, circuit breakers, and self-correction loops.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Processing Stages](#processing-stages)
3. [Core Components](#core-components)
4. [Intelligence Providers](#intelligence-providers)
5. [Error Handling & Recovery](#error-handling--recovery)
6. [Configuration](#configuration)
7. [API Reference](#api-reference)
8. [Testing](#testing)
9. [Troubleshooting](#troubleshooting)

---

## Architecture Overview

### Blackboard Pattern

All agents share a single `GlobalContext` (the Blackboard):

```
┌─────────────────────────────────────────────────────────────┐
│                    GLOBAL CONTEXT                            │
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
```

### Why Blackboard?

| Traditional CWD | Blackboard |
|-----------------|------------|
| Complex message passing | Shared state |
| Event-driven coordination | Stage-based routing |
| Hard to debug | Single source of truth |
| Overhead for simple tasks | Minimal complexity |

---

## Processing Stages

```python
class ProcessingStage(Enum):
    INGEST = "INGEST"           # Extract usage
    SYNTHESIS = "SYNTHESIS"      # Generate FAQs
    DRAFTING = "DRAFTING"        # Compare products
    VERIFICATION = "VERIFICATION" # Validate output
    COMPLETE = "COMPLETE"        # Done
```

| Stage | Worker | Input | Output |
|-------|--------|-------|--------|
| INGEST | UsageWorker | product_input | usage instructions |
| SYNTHESIS | QuestionsWorker | product_input | 20 FAQ tuples |
| DRAFTING | ComparisonWorker | both products | comparison dict |
| VERIFICATION | ValidationWorker | generated_content | is_valid bool |

---

## Core Components

### 1. GlobalContext

```python
class GlobalContext(BaseModel):
    # Stage tracking
    stage: ProcessingStage = ProcessingStage.INGEST
    
    # Immutable inputs
    product_input: Optional[ProductData]
    comparison_input: Optional[ProductData]
    
    # Generated content
    generated_content: ContentSchema
    
    # Validation
    errors: List[str] = []
    is_valid: bool = False
    
    # Reflexion (self-correction)
    reflexion_feedback: str = ""
    retry_count: int = 0
    
    # Tracing
    trace_id: str
    execution_history: List[str]
```

### 2. PriorityRouter

Simple boolean routing instead of complex bidding:

```python
class PriorityRouter:
    def select_next(self, context: GlobalContext) -> Optional[Agent]:
        for agent in self.agents:
            if agent.can_handle(context):
                return agent
        return None
```

### 3. Worker Pattern

```python
class QuestionsWorker:
    FAQ_BUFFER = 20      # Generate more than needed
    MIN_REQUIRED = 15    # Validation threshold
    
    def can_handle(self, state: GlobalContext) -> bool:
        return (
            state.stage == ProcessingStage.SYNTHESIS and
            len(state.generated_content.faq_questions) < self.MIN_REQUIRED
        )
    
    def run(self, context: GlobalContext) -> AgentResult:
        questions = generate_questions_by_category(...)
        context.generated_content.faq_questions = questions
        context.advance_stage(ProcessingStage.DRAFTING)
        return AgentResult(status=AgentStatus.COMPLETE, ...)
```

### 4. EventBus

Observer pattern for non-blocking logging:

```python
EventBus.emit(Events.AGENT_START, {"agent": "QuestionsWorker"}, trace_id)
EventBus.emit(Events.AGENT_COMPLETE, {"status": "COMPLETE"}, trace_id)
EventBus.emit(Events.REFLEXION_TRIGGERED, {"feedback": "..."}, trace_id)
```

---

## Intelligence Providers

### Provider Hierarchy

```
IIntelligenceProvider (ABC)
    │
    ├── MistralProvider
    │   └── API calls + retries + exponential backoff
    │
    └── OfflineRuleProvider
        └── Dynamic regex/template generation (NOT static mocks)
```

### CircuitBreaker

```python
class CircuitBreaker:
    failure_threshold = 3    # Opens after 3 failures
    reset_timeout = 60       # Seconds until half-open
    
    def record_failure(self):
        self.failures += 1
        if self.failures >= self.threshold:
            self.is_open = True  # Switch to offline
```

### OfflineRuleProvider

Dynamic generation from product data:
- Regex theme extraction from prompts
- Template interpolation with actual values
- Ingredient-benefit mapping

```python
def generate_faq(self, product_data: Dict) -> List[Tuple]:
    # Extract from product_data, NOT hardcoded
    name = product_data.get("name")
    return [
        (f"What is {name}?", f"{name} is a skincare product...", "Informational"),
        ...
    ]
```

---

## Error Handling & Recovery

### Reflexion Loop

When validation fails:

```
ValidationWorker rejects (< 15 FAQs)
    ↓
Orchestrator sets context.reflexion_feedback
    ↓
Stage reverts to SYNTHESIS
    ↓
QuestionsWorker sees feedback, retries
    ↓
Max 3 retries, then fail
```

### Error Types

| Error | Handler | Recovery |
|-------|---------|----------|
| Validation failure | Reflexion loop | Retry with feedback |
| LLM failure | CircuitBreaker | Switch to offline |
| Config missing | FileNotFoundError | User must fix |
| Schema error | Pydantic ValidationError | Logs detailed error |

---

## Configuration

### run_config.json

```json
{
  "product": {
    "name": "GlowBoost Vitamin C Serum",
    "brand": "GlowBoost",
    "concentration": "10% Vitamin C",
    "key_ingredients": ["Vitamin C", "Hyaluronic Acid"],
    "benefits": ["Brightening", "Fades dark spots"],
    "price": 699.0,
    "currency": "INR",
    "skin_types": ["Oily", "Combination"],
    "side_effects": "Mild tingling for sensitive skin",
    "usage_instructions": "Apply 2-3 drops morning before sunscreen"
  },
  "comparison_product": {
    "name": "RadiantGlow Vitamin C Cream",
    "brand": "RadiantGlow",
    "concentration": "15% Vitamin C",
    "key_ingredients": ["Vitamin C", "Ferulic Acid", "Vitamin E"],
    "benefits": ["Brightening", "Antioxidant protection"],
    "price": 899.0,
    "skin_types": ["Normal", "Dry", "Combination"]
  }
}
```

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MISTRAL_API_KEY` | No | None | Uses OfflineRuleProvider if absent |
| `RUN_CONFIG` | No | `config/run_config.json` | Custom config path |

---

## API Reference

### GlobalContext

| Method | Description |
|--------|-------------|
| `log_step(name)` | Add to execution_history |
| `advance_stage(stage)` | Move to next stage |
| `set_reflexion(feedback)` | Set error feedback, increment retry |

### PriorityRouter

| Method | Description |
|--------|-------------|
| `select_next(context)` | Returns first agent where can_handle=True |

### EventBus

| Method | Description |
|--------|-------------|
| `emit(event, data, trace_id)` | Non-blocking notification |
| `subscribe(callback)` | Add observer |
| `get_events(type)` | Get logged events |

### IIntelligenceProvider

| Method | Description |
|--------|-------------|
| `generate(prompt)` | Generate text |
| `generate_json(prompt)` | Generate and parse JSON |
| `generate_faq(product_data)` | Generate FAQ tuples |

---

## Testing

### Run Tests

```bash
pytest                              # All tests
pytest -v                           # Verbose
pytest --cov=skincare_agent_system  # Coverage
pytest tests/test_proposals.py      # Specific file
```

### Test Categories

| File | Tests |
|------|-------|
| `test_proposals.py` | PriorityRouter, can_handle |
| `test_workers.py` | Worker stage logic |
| `test_providers.py` | MistralProvider, OfflineRuleProvider |
| `test_models.py` | Pydantic validation |

---

## Troubleshooting

### "Config file not found"

```bash
# Check config exists
ls config/run_config.json

# Or use custom path
RUN_CONFIG=/path/to/config.json python run_agent.py
```

### "LLM failed after retries"

CircuitBreaker activated → Using OfflineRuleProvider  
This is expected behavior when API is unavailable.

### "Validation failed: FAQ count X < 15"

1. Check OfflineRuleProvider generates enough questions
2. Check product_data has required fields (name, ingredients)
3. Reflexion should auto-retry up to 3 times

### "No agent can handle current state"

Stage may have advanced incorrectly. Check:
1. Worker `can_handle()` logic
2. `context.stage` value
3. Preconditions (e.g., product_input exists)

---

## Output Files

| File | Content | Format |
|------|---------|--------|
| `output/faq.json` | 20 Q&A pairs | `{product, questions: [{q, a, category}]}` |
| `output/product_page.json` | Product details | `{name, benefits, ingredients, price}` |
| `output/comparison_page.json` | Comparison | `{primary, other, recommendation}` |

---

## Requirements Compliance

| Requirement | Status | Implementation |
|-------------|--------|----------------|
| ≥15 FAQ questions | ✅ | Generates 20 with 15 threshold |
| Autonomous agents | ✅ | can_handle() + Reflexion |
| No hardcoded data | ✅ | run_config.json injection |
| LLM integration | ✅ | MistralProvider + fallback |
| Traceability | ✅ | EventBus + JSON logging |
| Self-correction | ✅ | Reflexion feedback loop |
| Machine-readable output | ✅ | JSON files |
