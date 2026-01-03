# Implementation Guide

**Technical reference for developers working with the Kasparro Content Generation System**

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Core Components](#core-components)
3. [Implementation Patterns](#implementation-patterns)
4. [Data Models](#data-models)
5. [Agent Implementation](#agent-implementation)
6. [LLM Integration](#llm-integration)
7. [Error Handling](#error-handling)
8. [Testing Strategy](#testing-strategy)
9. [Extension Guide](#extension-guide)

---

## Architecture Overview

### Blackboard Pattern

The system implements a **Blackboard architecture** where all agents share a single `GlobalContext`:

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

### Processing Stages

```python
class ProcessingStage(str, Enum):
    INGEST = "INGEST"           # Extract usage instructions
    SYNTHESIS = "SYNTHESIS"      # Generate FAQ questions
    DRAFTING = "DRAFTING"        # Create product comparisons
    VERIFICATION = "VERIFICATION" # Validate outputs
    COMPLETE = "COMPLETE"        # Workflow finished
```

### Component Hierarchy

```
skincare_agent_system/
├── core/                    # Core orchestration
│   ├── models.py           # Data models (GlobalContext, ProductData)
│   ├── orchestrator.py     # Main execution loop
│   ├── proposals.py        # PriorityRouter
│   ├── event_bus.py        # Observer pattern
│   └── validators.py       # Schema validation
├── actors/                  # Agent workers
│   ├── base_agent.py       # Base agent interface
│   └── workers.py          # Specialized workers
├── infrastructure/          # External services
│   ├── providers.py        # LLM abstraction
│   └── logger.py           # JSON logging
├── logic_blocks/           # Business logic
│   ├── question_generator.py
│   ├── comparison_block.py
│   └── usage_block.py
└── templates/              # Output rendering
    ├── faq_template.py
    ├── product_page_template.py
    └── comparison_template.py
```

---

## Core Components

### 1. GlobalContext (Blackboard)

**File**: `core/models.py`

The shared state object that all agents read from and write to:

```python
class GlobalContext(BaseModel):
    """
    The Blackboard - single source of truth for all agents.
    Immutable input + mutable artifacts + validation state + reflexion.
    """
    
    # Processing stage
    stage: ProcessingStage = ProcessingStage.INGEST
    
    # Immutable inputs (set once at start)
    product_input: Optional[ProductData] = None
    comparison_input: Optional[ProductData] = None
    
    # Generated content (artifacts)
    generated_content: ContentSchema = Field(default_factory=ContentSchema)
    
    # Validation state
    errors: List[str] = Field(default_factory=list)
    is_valid: bool = False
    
    # Reflexion (self-correction)
    reflexion_feedback: str = ""
    retry_count: int = 0
    
    # Metadata
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    execution_history: List[str] = Field(default_factory=list)
    
    def log_step(self, step_name: str):
        """Add step to execution history"""
        self.execution_history.append(step_name)
    
    def advance_stage(self, new_stage: ProcessingStage):
        """Move to next processing stage"""
        self.stage = new_stage
    
    def set_reflexion(self, feedback: str):
        """Set reflexion feedback for retry"""
        self.reflexion_feedback = feedback
        self.retry_count += 1
```

**Key Features**:
- Pydantic validation ensures type safety
- Immutable inputs prevent accidental modification
- Execution history for debugging
- Trace ID for distributed tracing

### 2. Orchestrator

**File**: `core/orchestrator.py`

Main execution loop that coordinates all agents:

```python
class Orchestrator:
    """Stage-based orchestrator with Reflexion self-correction loop"""
    
    MAX_RETRIES = 3
    
    def __init__(self, max_steps: int = 20):
        self.agents: Dict[str, object] = {}
        self.max_steps = max_steps
        self.router: Optional[PriorityRouter] = None
    
    def register_agent(self, agent: object):
        """Add agent to pool"""
        self.agents[agent.name] = agent
    
    def run(self, context: GlobalContext) -> GlobalContext:
        """
        Main loop: Check can_handle → Execute → Reflexion on failure
        """
        self.router = PriorityRouter(list(self.agents.values()))
        
        step = 0
        while step < self.max_steps:
            step += 1
            
            # Check completion
            if context.stage == ProcessingStage.COMPLETE:
                break
            
            # Select agent
            agent = self.router.select_next(context)
            if not agent:
                self._advance_stage_if_stuck(context)
                continue
            
            # Execute agent
            result = agent.run(context, directive)
            context = result.context
            
            # Handle validation failure - REFLEXION LOOP
            if result.status == AgentStatus.VALIDATION_FAILED:
                if context.retry_count < self.MAX_RETRIES:
                    feedback = self._build_reflexion_prompt(result.message, context)
                    context.set_reflexion(feedback)
                    context.stage = ProcessingStage.SYNTHESIS  # Retry
                    continue
                else:
                    break  # Max retries exceeded
        
        return context
```

### 3. PriorityRouter

**File**: `core/proposals.py`

Simple boolean routing instead of complex bidding:

```python
class PriorityRouter:
    """Simple can_handle() boolean routing"""
    
    def __init__(self, agents: List[object]):
        self.agents = agents
    
    def select_next(self, context: GlobalContext) -> Optional[object]:
        """Returns first agent where can_handle=True"""
        for agent in self.agents:
            if agent.can_handle(context):
                return agent
        return None
```

### 4. EventBus

**File**: `core/event_bus.py`

Observer pattern for non-blocking event logging:

```python
class EventBus:
    """Lightweight observer pattern for state change notifications"""
    
    _subscribers: List[Callable] = []
    _event_log: List[Dict[str, Any]] = []
    
    @classmethod
    def emit(cls, event: str, data: Dict[str, Any] = None, trace_id: str = None):
        """Emit event to all subscribers (non-blocking)"""
        event_data = {
            "timestamp": datetime.now().isoformat(),
            "event": event,
            "data": data or {},
            "trace_id": trace_id,
        }
        
        cls._event_log.append(event_data)
        
        # Notify subscribers asynchronously
        for sub in cls._subscribers:
            Thread(target=sub, args=(event, event_data), daemon=True).start()
```

**Standard Events**:
- `STATE_CHANGE`: Stage transitions
- `AGENT_START`: Agent execution begins
- `AGENT_COMPLETE`: Agent finishes
- `AGENT_ERROR`: Agent encounters error
- `REFLEXION_TRIGGERED`: Self-correction activated
- `WORKFLOW_COMPLETE`: All stages finished

---

## Implementation Patterns

### 1. Stage-Based Routing

Each worker implements `can_handle()` to determine if it should execute:

```python
class UsageWorker:
    def can_handle(self, state: GlobalContext) -> bool:
        return (
            state.stage == ProcessingStage.INGEST and
            not state.generated_content.usage
        )
```

**Benefits**:
- Deterministic agent selection
- Easy to debug and test
- No complex scoring algorithms

### 2. Reflexion Self-Correction

When validation fails, the system automatically retries with feedback:

```python
# In ValidationWorker
if len(faq_questions) < 15:
    return AgentResult(
        agent_name=self.name,
        status=AgentStatus.VALIDATION_FAILED,
        context=context,
        message=f"Only {len(faq_questions)} questions, need 15"
    )

# In Orchestrator
if result.status == AgentStatus.VALIDATION_FAILED:
    feedback = f"Generated {current_count}, need {15 - current_count} more"
    context.set_reflexion(feedback)
    context.stage = ProcessingStage.SYNTHESIS  # Retry
```

### 3. Provider Abstraction

LLM integration is abstracted through `IIntelligenceProvider`:

```python
class IIntelligenceProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        pass
    
    @abstractmethod
    def generate_faq(self, product_data: Dict) -> List[Tuple[str, str, str]]:
        pass

class MistralProvider(IIntelligenceProvider):
    def generate(self, prompt: str, **kwargs) -> str:
        # Retry logic with exponential backoff
        for attempt in range(self.max_retries):
            try:
                response = client.chat(model=model, messages=[...])
                return response.choices[0].message.content
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise
                time.sleep(2**attempt)  # Exponential backoff
```

### 4. Observer EventBus

Non-blocking event emission for traceability:

```python
# Emit events without blocking workflow
EventBus.emit(Events.AGENT_START, {"agent": "QuestionsWorker"}, trace_id)
EventBus.emit(Events.AGENT_COMPLETE, {"status": "COMPLETE"}, trace_id)

# Subscribe to events
def log_handler(event: str, data: Dict):
    logger.info(f"Event: {event}", extra=data)

EventBus.subscribe(log_handler)
```

---

## Data Models

### ProductData

```python
class ProductData(BaseModel):
    """Strict schema for product data with validation"""
    
    name: str = Field(..., min_length=1)
    brand: str = Field(..., min_length=1)
    category: str = Field(default="General")
    concentration: Optional[str] = None
    key_ingredients: List[str] = Field(default_factory=list)
    benefits: List[str] = Field(default_factory=list)
    price: Optional[float] = Field(None, ge=0)
    currency: str = "INR"
    skin_types: List[str] = Field(default_factory=list)
    side_effects: Optional[str] = None
    usage_instructions: Optional[str] = None
    
    @field_validator("skin_types")
    @classmethod
    def validate_skin_types(cls, v):
        valid_types = ["Oily", "Dry", "Combination", "Sensitive", "Normal", "All"]
        # Validation logic
        return v
```

### FAQQuestion

```python
class FAQQuestion(BaseModel):
    """Single FAQ question-answer pair with validation"""
    
    question: str = Field(..., min_length=5)
    answer: str = Field(..., min_length=10)
    category: str = Field(default="General")
    
    @field_validator("category")
    @classmethod
    def validate_category(cls, v):
        valid = ["Informational", "Safety", "Usage", "Purchase", "Comparison", 
                 "Ingredients", "General"]
        if v not in valid:
            return "General"
        return v
```

### AgentResult

```python
class AgentResult(BaseModel):
    """Standardized return object for all agents"""
    
    agent_name: str
    status: AgentStatus
    context: GlobalContext
    message: str = ""
```

---

## Agent Implementation

### Worker Pattern

All workers follow this pattern:

```python
class WorkerTemplate:
    """Template for implementing new workers"""
    
    def __init__(self, name: str = "WorkerTemplate"):
        self.name = name
    
    def can_handle(self, state: GlobalContext) -> bool:
        """
        Return True if this worker should execute.
        Check stage and preconditions.
        """
        return (
            state.stage == ProcessingStage.YOUR_STAGE and
            # Additional preconditions
        )
    
    def run(self, context: GlobalContext, directive: Optional[TaskDirective] = None) -> AgentResult:
        """
        Execute worker logic.
        Modify context.
        Return result with status.
        """
        try:
            # 1. Perform work
            result = self._do_work(context)
            
            # 2. Update context
            context.generated_content.your_field = result
            
            # 3. Advance stage
            context.advance_stage(ProcessingStage.NEXT_STAGE)
            
            # 4. Return success
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.COMPLETE,
                context=context,
                message="Work completed successfully"
            )
        
        except Exception as e:
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.ERROR,
                context=context,
                message=str(e)
            )
```

### Example: QuestionsWorker

```python
class QuestionsWorker:
    """Generate FAQ questions - activates at SYNTHESIS stage"""
    
    FAQ_BUFFER = 20
    MIN_FAQ_QUESTIONS = 15
    
    def can_handle(self, state: GlobalContext) -> bool:
        return (
            state.stage == ProcessingStage.SYNTHESIS and
            len(state.generated_content.faq_questions) < self.MIN_FAQ_QUESTIONS
        )
    
    def run(self, context: GlobalContext, directive: Optional[TaskDirective] = None) -> AgentResult:
        # Generate questions using LLM
        questions = generate_questions_by_category(
            context.product_input,
            target_count=self.FAQ_BUFFER,
            reflexion_feedback=context.reflexion_feedback
        )
        
        # Update context
        context.generated_content.faq_questions = questions
        context.advance_stage(ProcessingStage.DRAFTING)
        
        return AgentResult(
            agent_name=self.name,
            status=AgentStatus.COMPLETE,
            context=context,
            message=f"Generated {len(questions)} questions"
        )
```

---

## LLM Integration

### MistralProvider Implementation

```python
class MistralProvider(IIntelligenceProvider):
    """LLM integration via Mistral AI"""
    
    def __init__(self, max_retries: int = 3):
        self.api_key = os.getenv("MISTRAL_API_KEY")
        self.max_retries = max_retries
        self._client = None
    
    def generate(self, prompt: str, **kwargs) -> str:
        """Generate text using Mistral AI with retries"""
        temperature = kwargs.get("temperature", 0.7)
        model = kwargs.get("model", "mistral-small-latest")
        
        client = self._get_client()
        
        for attempt in range(self.max_retries):
            try:
                response = client.chat(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                )
                
                if response and response.choices:
                    return response.choices[0].message.content
                
                raise ValueError("Empty response from Mistral")
            
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise
                time.sleep(2**attempt)  # Exponential backoff
    
    def generate_faq(self, product_data: Dict) -> List[Tuple[str, str, str]]:
        """Generate FAQs using Mistral"""
        prompt = f"""Generate exactly 20 FAQ questions for {product_data['name']}.
        Return JSON: [{{"question": "...", "answer": "...", "category": "..."}}]"""
        
        response = self.generate(prompt, temperature=0.5)
        
        # Clean markdown if present
        cleaned = response.strip()
        if "```json" in cleaned:
            cleaned = cleaned.split("```json")[1].split("```")[0]
        
        faqs = json.loads(cleaned.strip())
        
        return [
            (faq["question"], faq["answer"], faq["category"])
            for faq in faqs[:20]
        ]
```

---

## Error Handling

### Validation Errors

```python
class ValidationWorker:
    def run(self, context: GlobalContext, directive: Optional[TaskDirective] = None) -> AgentResult:
        faq_count = len(context.generated_content.faq_questions)
        
        # Check FAQ count
        if faq_count < self.MIN_FAQ_QUESTIONS:
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.VALIDATION_FAILED,
                context=context,
                message=f"FAQ count {faq_count} < {self.MIN_FAQ_QUESTIONS}"
            )
        
        # Check safety policy
        is_safe, error_msg = self._check_safety_policy(context.generated_content.faq_questions)
        if not is_safe:
            context.errors.append(error_msg)
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.VALIDATION_FAILED,
                context=context,
                message=error_msg
            )
        
        # All validations passed
        context.is_valid = True
        context.advance_stage(ProcessingStage.COMPLETE)
        
        return AgentResult(
            agent_name=self.name,
            status=AgentStatus.COMPLETE,
            context=context,
            message="Validation passed"
        )
```

### LLM Failures

```python
# Retry with exponential backoff
for attempt in range(max_retries):
    try:
        return llm_call()
    except Exception as e:
        if attempt == max_retries - 1:
            logger.error(f"LLM failed after {max_retries} retries")
            raise
        wait_time = 2**attempt
        logger.warning(f"Attempt {attempt + 1} failed, retrying in {wait_time}s")
        time.sleep(wait_time)
```

---

## Testing Strategy

### Unit Tests

```python
# Test worker can_handle logic
def test_usage_worker_can_handle():
    context = GlobalContext(
        stage=ProcessingStage.INGEST,
        product_input=ProductData(name="Test", brand="Test")
    )
    
    worker = UsageWorker()
    assert worker.can_handle(context) == True
    
    context.generated_content.usage = "Some usage"
    assert worker.can_handle(context) == False
```

### Integration Tests

```python
# Test full workflow
def test_full_workflow():
    context = load_config()
    orchestrator = Orchestrator()
    
    orchestrator.register_agent(UsageWorker())
    orchestrator.register_agent(QuestionsWorker())
    orchestrator.register_agent(ComparisonWorker())
    orchestrator.register_agent(ValidationWorker())
    
    final_context = orchestrator.run(context)
    
    assert final_context.stage == ProcessingStage.COMPLETE
    assert final_context.is_valid == True
    assert len(final_context.generated_content.faq_questions) >= 15
```

### Mocking LLM Calls

```python
@patch('infrastructure.providers.MistralProvider.generate_faq')
def test_questions_worker(mock_generate_faq):
    mock_generate_faq.return_value = [
        ("Q1", "A1", "Informational"),
        # ... 19 more
    ]
    
    worker = QuestionsWorker()
    result = worker.run(context)
    
    assert result.status == AgentStatus.COMPLETE
    assert len(context.generated_content.faq_questions) == 20
```

---

## Extension Guide

### Adding a New Worker

1. **Create worker class**:
```python
class NewWorker:
    def __init__(self, name: str = "NewWorker"):
        self.name = name
    
    def can_handle(self, state: GlobalContext) -> bool:
        return state.stage == ProcessingStage.YOUR_STAGE
    
    def run(self, context: GlobalContext, directive: Optional[TaskDirective] = None) -> AgentResult:
        # Your logic here
        pass
```

2. **Register in orchestrator**:
```python
orchestrator.register_agent(NewWorker())
```

3. **Add tests**:
```python
def test_new_worker_can_handle():
    # Test logic
    pass
```

### Adding a New Processing Stage

1. **Update ProcessingStage enum**:
```python
class ProcessingStage(str, Enum):
    # ... existing stages
    YOUR_NEW_STAGE = "YOUR_NEW_STAGE"
```

2. **Update stage order in orchestrator**:
```python
stage_order = [
    ProcessingStage.INGEST,
    ProcessingStage.SYNTHESIS,
    ProcessingStage.YOUR_NEW_STAGE,  # Add here
    ProcessingStage.DRAFTING,
    # ...
]
```

3. **Create worker for new stage**

### Adding a New LLM Provider

1. **Implement IIntelligenceProvider**:
```python
class NewProvider(IIntelligenceProvider):
    @property
    def name(self) -> str:
        return "NewProvider"
    
    def generate(self, prompt: str, **kwargs) -> str:
        # Implementation
        pass
    
    def generate_faq(self, product_data: Dict) -> List[Tuple[str, str, str]]:
        # Implementation
        pass
```

2. **Update provider factory**:
```python
def get_provider() -> IIntelligenceProvider:
    provider_type = os.getenv("LLM_PROVIDER", "mistral")
    
    if provider_type == "mistral":
        return MistralProvider()
    elif provider_type == "new":
        return NewProvider()
```

---

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MISTRAL_API_KEY` | No | None | Mistral AI API key |
| `RUN_CONFIG` | No | `config/run_config.json` | Product config path |
| `LLM_MODEL` | No | `open-mistral-7b` | Mistral model name |

### Run Configuration

**File**: `config/run_config.json`

```json
{
  "product": {
    "name": "Product Name",
    "brand": "Brand Name",
    "key_ingredients": ["Ingredient 1", "Ingredient 2"],
    "benefits": ["Benefit 1", "Benefit 2"],
    "price": 699.0,
    "currency": "INR",
    "skin_types": ["Oily", "Combination"]
  },
  "comparison_product": {
    "name": "Comparison Product",
    "brand": "Other Brand",
    "key_ingredients": ["Ingredient 1", "Ingredient 3"],
    "price": 899.0
  }
}
```

---

## Run Commands

```bash
# Run system with default config
python run_agent.py

# Run with custom config
RUN_CONFIG=custom.json python run_agent.py

# Run tests
pytest

# Run tests with coverage
pytest --cov=skincare_agent_system

# Run specific test file
pytest tests/test_workers.py -v

# Format code
black .

# Lint code
flake8
```

---

## Output Files

| File | Content | Schema |
|------|---------|--------|
| `output/faq.json` | 20 categorized Q&A pairs | `{product_name, total_questions, questions: [{q, a, category}]}` |
| `output/product_page.json` | Product details | `{name, brand, benefits, ingredients, price, usage}` |
| `output/comparison_page.json` | Product comparison | `{primary, other, differences, recommendation, winner_categories}` |
| `output/trace.log` | JSON structured logs | `{timestamp, agent, level, action, trace_id}` |

---

## Performance Considerations

### Latency
- **LLM Calls**: 2-5 seconds per call
- **Total Workflow**: 10-30 seconds (with LLM)
- **Offline Mode**: 1-3 seconds (rule-based)

### Optimization Tips
1. **Reduce LLM Calls**: Cache frequently used prompts
2. **Batch Processing**: Process multiple products in parallel
3. **Async Execution**: Use async/await for I/O operations
4. **Connection Pooling**: Reuse HTTP connections

---

## Troubleshooting

### Common Issues

**"No agent can handle current state"**
- Check `can_handle()` logic in workers
- Verify `context.stage` is correct
- Ensure preconditions are met

**"Validation failed: FAQ count < 15"**
- Check LLM is generating enough questions
- Verify product data has required fields
- Reflexion will auto-retry up to 3 times

**"LLM API failed"**
- Verify `MISTRAL_API_KEY` is set
- Check API quota and rate limits
- System will retry with exponential backoff

---

## Best Practices

1. **Always use Pydantic models** for data validation
2. **Emit events** for important state changes
3. **Add trace IDs** to all log messages
4. **Test can_handle() logic** thoroughly
5. **Handle LLM failures** gracefully
6. **Keep workers focused** on single responsibility
7. **Document complex logic** with comments
8. **Use type hints** for better IDE support

---

**For detailed system design, see [docs/projectdocumentation.md](docs/projectdocumentation.md)**
