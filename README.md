# Kasparro Content Generation System

**An autonomous multi-agent system for intelligent skincare content generation using Blackboard architecture and LLM-powered reasoning.**

---

## 🎯 Overview

The Kasparro Content Generation System is a production-ready, autonomous multi-agent framework designed to generate high-quality, structured skincare product content. Built on the **Blackboard architectural pattern**, the system orchestrates specialized agents that collaborate through a shared state to produce FAQ pages, product descriptions, and comparative analyses.

### Core Value Proposition

- **Autonomous Operation**: Self-correcting agents that adapt and retry without human intervention
- **Intelligent Content Generation**: LLM-powered reasoning with fallback mechanisms
- **Structured Output**: Machine-readable JSON outputs ready for integration
- **Production-Ready**: Comprehensive error handling, logging, and observability
- **Extensible Architecture**: Clean abstractions for adding new agents and capabilities

---

## ✨ Features

### Multi-Agent Orchestration
- **Stage-Based Routing**: Agents activate based on processing stages (INGEST → SYNTHESIS → DRAFTING → VERIFICATION → COMPLETE)
- **Blackboard Pattern**: Shared `GlobalContext` eliminates complex message passing
- **Priority Routing**: Simple `can_handle()` boolean logic for agent selection
- **Event-Driven Logging**: Non-blocking observer pattern for complete traceability

### Intelligent Content Generation
- **LLM Integration**: Mistral AI provider with retry logic and exponential backoff
- **Dynamic FAQ Generation**: Produces 20 categorized question-answer pairs per product
- **Product Comparison**: Automated comparative analysis with recommendations
- **Usage Extraction**: Intelligent parsing of product usage instructions

### Self-Correction & Reliability
- **Reflexion Loop**: Automatic retry with feedback when validation fails
- **Circuit Breaker**: Graceful degradation when external services fail
- **Schema Validation**: Pydantic models ensure data integrity
- **Comprehensive Logging**: JSON structured logs with trace IDs for debugging

### Configuration & Deployment
- **External Configuration**: Product data injected via JSON (no hardcoding)
- **Environment-Based Setup**: API keys and settings via `.env` files
- **Flexible Templates**: Jinja2-based rendering for customizable output formats
- **Test Coverage**: Comprehensive pytest suite with mocking

---

## 🏗️ Architecture

### Blackboard Pattern

The system uses a **Blackboard architecture** where all agents read from and write to a shared `GlobalContext`:

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

### Processing Stages

| Stage | Worker | Responsibility | Output |
|-------|--------|---------------|--------|
| **INGEST** | `UsageWorker` | Extract usage instructions from product data | Usage text |
| **SYNTHESIS** | `QuestionsWorker` | Generate 20 FAQ questions using LLM | FAQ tuples (Q, A, Category) |
| **DRAFTING** | `ComparisonWorker` | Compare products and generate recommendations | Comparison dict |
| **VERIFICATION** | `ValidationWorker` | Validate ≥15 FAQs and safety policies | Validation status |
| **COMPLETE** | - | Workflow finished | Final JSON outputs |

### Key Components

| Component | Location | Purpose |
|-----------|----------|---------|
| **GlobalContext** | `core/models.py` | Pydantic model - shared state blackboard |
| **PriorityRouter** | `core/proposals.py` | Agent selection via `can_handle()` |
| **Orchestrator** | `core/orchestrator.py` | Stage-based execution loop with Reflexion |
| **Workers** | `actors/workers.py` | Specialized agents (Usage, Questions, Comparison, Validation) |
| **EventBus** | `core/event_bus.py` | Observer pattern for async logging |
| **Providers** | `infrastructure/providers.py` | LLM abstraction (Mistral AI) |
| **Templates** | `templates/` | Jinja2 templates for JSON output rendering |

---

## 🚀 Tech Stack

### Core Technologies
- **Python 3.8+**: Primary language
- **Pydantic 2.0+**: Schema validation and data modeling
- **Mistral AI**: LLM provider for content generation
- **Jinja2**: Template rendering engine

### Architecture & Patterns
- **LangGraph**: Agent orchestration framework
- **LangChain Core**: Agent abstractions and utilities
- **Blackboard Pattern**: Shared state architecture
- **Observer Pattern**: Event-driven logging

### Development & Testing
- **pytest**: Testing framework with coverage
- **Black**: Code formatting
- **isort**: Import sorting
- **flake8**: Linting
- **pre-commit**: Git hooks for code quality

### Environment & Configuration
- **python-dotenv**: Environment variable management
- **JSON**: External configuration files

---

## 📦 Setup

### Prerequisites

- Python 3.8 or higher
- pip package manager
- (Optional) Mistral API key for LLM features

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/Sarvagya1212/kasparro-agentic-sarvagya-jain.git
   cd kasparro-content-generation
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env and add your MISTRAL_API_KEY (optional)
   ```

4. **Verify installation**
   ```bash
   python run_agent.py
   ```

---

## 🎮 Usage

### Basic Execution

Run the system with default configuration:

```bash
python run_agent.py
```

**Output**: Three JSON files in `output/` directory:
- `faq.json` - 20 categorized FAQ questions
- `product_page.json` - Product details and specifications
- `comparison_page.json` - Product comparison with recommendations

### Custom Configuration

Override the default product configuration:

```bash
RUN_CONFIG=path/to/custom_config.json python run_agent.py
```

### Configuration File Format

Create a `config/run_config.json` file:

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

---

## 🔧 Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MISTRAL_API_KEY` | No | None | Mistral AI API key for LLM-powered generation. System works without it using rule-based fallback. |
| `RUN_CONFIG` | No | `config/run_config.json` | Path to product configuration file |
| `LLM_MODEL` | No | `open-mistral-7b` | Mistral model to use for generation |

### Getting a Mistral API Key

1. Visit [https://console.mistral.ai/](https://console.mistral.ai/)
2. Create an account and generate an API key
3. Add to `.env` file: `MISTRAL_API_KEY=your_key_here`

---

## 🏃 Build & Run

### Development Mode

```bash
# Run with default configuration
python run_agent.py

# Run with custom config
RUN_CONFIG=custom.json python run_agent.py

# Run tests
pytest

# Run tests with coverage
pytest --cov=skincare_agent_system

# Run specific test file
pytest tests/test_workers.py -v
```

### Code Quality

```bash
# Format code
black .

# Sort imports
isort .

# Lint code
flake8

# Run all pre-commit hooks
pre-commit run --all-files
```

### Output Files

Generated files are saved to `output/`:

**`faq.json`** - FAQ page with 20 questions
```json
{
  "product_name": "GlowBoost Vitamin C Serum",
  "total_questions": 20,
  "questions": [
    {
      "question": "What is Vitamin C Serum?",
      "answer": "A concentrated skincare product...",
      "category": "Informational"
    }
  ]
}
```

**`product_page.json`** - Product details
```json
{
  "name": "GlowBoost Vitamin C Serum",
  "brand": "GlowBoost",
  "benefits": ["Brightening", "Fades dark spots"],
  "price": 699.0,
  "currency": "INR"
}
```

**`comparison_page.json`** - Product comparison
```json
{
  "primary": { "name": "GlowBoost Vitamin C Serum", ... },
  "other": { "name": "RadiantGlow Vitamin C Cream", ... },
  "recommendation": "GlowBoost is better for...",
  "winner_categories": { "price": "GlowBoost", ... }
}
```

---

## 🧪 Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run with coverage report
pytest --cov=skincare_agent_system --cov-report=html

# Run specific test file
pytest tests/test_workers.py

# Run specific test function
pytest tests/test_workers.py::test_usage_worker_can_handle
```

### Test Structure

```
tests/
├── test_outputs.py      # Output validation tests
├── test_requirements.py # Requirements compliance tests
├── test_validation.py   # Schema validation tests
└── test_workers.py      # Worker agent tests
```

---

## 🤝 Contributing

### Development Workflow

1. **Fork the repository**
2. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Make your changes**
   - Follow existing code style
   - Add tests for new features
   - Update documentation

4. **Run quality checks**
   ```bash
   black .
   isort .
   flake8
   pytest
   ```

5. **Commit your changes**
   ```bash
   git commit -m "feat: add new feature"
   ```

6. **Push and create a pull request**
   ```bash
   git push origin feature/your-feature-name
   ```

### Code Style Guidelines

- Follow PEP 8 conventions
- Use type hints for function signatures
- Write docstrings for classes and functions
- Keep functions focused and single-purpose
- Maximum line length: 100 characters

### Adding New Agents

1. Create worker class in `actors/workers.py`
2. Implement `can_handle(state)` method
3. Implement `run(context, directive)` method
4. Register in `run_agent.py`
5. Add tests in `tests/test_workers.py`

---

## 📄 License

MIT License - See LICENSE file for details

---

## 📚 Additional Documentation

- **System Design**: See [docs/projectdocumentation.md](docs/projectdocumentation.md) for detailed architecture
- **Implementation Details**: See [IMPLEMENTATION.md](IMPLEMENTATION.md) for technical overview
- **API Reference**: See inline docstrings and type hints

---

## 🐛 Troubleshooting

### Common Issues

**"Config file not found"**
```bash
# Ensure config exists
ls config/run_config.json

# Or specify custom path
RUN_CONFIG=/path/to/config.json python run_agent.py
```

**"Validation failed: FAQ count < 15"**
- Check product data has required fields (name, ingredients)
- Reflexion loop will auto-retry up to 3 times
- Verify LLM provider is working correctly

**"No agent can handle current state"**
- Check worker `can_handle()` logic
- Verify `context.stage` value is correct
- Ensure preconditions are met (e.g., product_input exists)

### Debug Mode

Enable detailed logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Check trace logs:
```bash
cat output/trace.log
```

---

## 📞 Support

For issues, questions, or contributions:
- Open an issue on GitHub
- Review existing documentation in `docs/`
- Check conversation history for context

---

**Built using autonomous multi-agent architecture**
