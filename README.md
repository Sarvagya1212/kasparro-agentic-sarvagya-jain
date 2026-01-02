# Skincare Agent System (SAS)

**An autonomous multi-agent system for intelligent skincare content generation using dynamic proposal-based orchestration.**

---

## Overview

The Skincare Agent System is a production-grade, autonomous multi-agent framework that generates structured content for skincare products. Unlike traditional rule-based systems, SAS implements **true agent autonomy** where agents independently assess context, propose actions, and coordinate dynamically through a proposal system—demonstrating advanced agentic AI patterns.

### Core Value Proposition

- **Autonomous Decision-Making**: Agents propose actions based on context assessment, not hardcoded workflows
- **Dynamic Orchestration**: Proposal-based coordination eliminates rigid execution paths
- **Production-Ready Security**: Multi-layered guardrails, credential isolation, and PII protection
- **LLM-Powered Reasoning**: Optional Mistral 7B integration for advanced cognitive capabilities
- **Verifiable Traceability**: Complete audit trails for all agent decisions and actions

---

## Key Features

### 🤖 Agent Autonomy
- **Proposal System**: Agents independently propose actions with confidence scores
- **Dynamic Selection**: Orchestrator selects best proposal based on priority and confidence
- **Self-Reflection**: Agents critique their own outputs and self-correct
- **Goal-Based Reasoning**: Agents work toward explicit goals, not just tasks

### 🏗️ Architecture
- **Coordinator-Worker-Delegator (CWD)** pattern for hierarchical task management
- **Event-Driven Communication**: Agents communicate via event bus, not direct calls
- **State Management**: Centralized state tracking with checkpoint/rollback support
- **LangGraph Integration**: Optional graph-based workflow orchestration

### 🔒 Security & Safety
- **Credential Shim**: Agents never access API keys directly—credentials injected at network layer
- **Injection Defense**: Multi-pattern prompt injection detection and blocking
- **PII Redaction**: Automatic filtering of personally identifiable information
- **Role Compliance**: Agents restricted to authorized tools and actions
- **Human-in-the-Loop (HITL)**: Optional approval gates for critical operations

### 🧠 Cognitive Capabilities
- **ReAct Pattern**: Reasoning + Acting for complex problem-solving
- **Chain of Thought (CoT)**: Step-by-step reasoning with LLM support
- **Tree of Thoughts (ToT)**: Explore multiple reasoning paths
- **Hierarchical Task Networks (HTN)**: Decompose complex goals into subtasks

### 📊 Content Generation
- **FAQ Generation**: Categorized Q&A pairs (15+ questions minimum)
- **Product Pages**: Structured JSON with benefits, usage, pricing
- **Comparison Analysis**: Side-by-side product comparisons with recommendations
- **Template System**: Jinja2-based rendering for consistent output

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| **Language** | Python 3.9+ |
| **LLM** | Mistral 7B (via API) |
| **Orchestration** | LangGraph, Custom Proposal System |
| **Data Validation** | Pydantic 2.0+ |
| **Templating** | Jinja2 |
| **Testing** | Pytest (174 tests) |
| **Code Quality** | Black, isort, flake8, pre-commit |
| **CI/CD** | GitHub Actions |

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      ORCHESTRATOR                            │
│  (Dynamic Proposal-Based Coordinator)                       │
└──────────────┬──────────────────────────────────────────────┘
               │
               │ Collects Proposals
               ▼
    ┌──────────────────────────────────────┐
    │      PROPOSAL SYSTEM                  │
    │  • Agents propose actions             │
    │  • Confidence scoring                 │
    │  • Priority-based selection           │
    └──────────────────────────────────────┘
               │
               │ Selects Best Proposal
               ▼
┌──────────────────────────────────────────────────────────────┐
│                        AGENTS                                 │
├───────────────┬──────────────┬──────────────┬────────────────┤
│  DataAgent    │ Delegator    │ Generation   │ Verifier       │
│  (Loader)     │ (Manager)    │ (Producer)   │ (Auditor)      │
└───────────────┴──────────────┴──────────────┴────────────────┘
                      │
                      │ Delegates to Workers
                      ▼
        ┌─────────────────────────────────────┐
        │         WORKER AGENTS                │
        │  • Benefits  • Usage  • Questions    │
        │  • Comparison  • Validation          │
        └─────────────────────────────────────┘
```

### Data Flow

1. **Data Loading**: `DataAgent` fetches and validates product data
2. **Synthetic Generation**: `SyntheticDataAgent` creates comparison products
3. **Analysis**: `DelegatorAgent` coordinates workers for content extraction
4. **Generation**: `GenerationAgent` renders templates into JSON
5. **Verification**: `VerifierAgent` performs independent safety/quality audits

---

## Quick Start

### Prerequisites

- Python 3.9 or higher
- (Optional) Mistral API key for LLM features

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/kasparro-content-generation.git
cd kasparro-content-generation

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env

# (Optional) Add your Mistral API key to .env
# MISTRAL_API_KEY=your_key_here
```

### Running the System

```bash
# Run the main pipeline
python -m skincare_agent_system.main

# Run with pytest
pytest

# Run specific tests
pytest tests/test_proposals.py -v
```

### Expected Output

The system generates three JSON files in the `output/` directory:

- `faq.json` - 15+ categorized FAQ questions
- `product_page.json` - Structured product information
- `comparison_page.json` - Side-by-side product comparison

---

## Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `MISTRAL_API_KEY` | Mistral AI API key | No | None (heuristic mode) |
| `LLM_MODEL` | Model identifier | No | `open-mistral-7b` |

**Note**: The system gracefully degrades to heuristic logic if no API key is provided.

---

## Project Structure

```
kasparro-content-generation/
├── skincare_agent_system/
│   ├── core/                 # Orchestration & state management
│   │   ├── orchestrator.py   # Dynamic coordinator
│   │   ├── proposals.py      # Proposal system
│   │   ├── models.py         # Pydantic data models
│   │   ├── state_manager.py  # State tracking
│   │   └── workflow_graph.py # LangGraph integration
│   ├── actors/               # Agents & workers
│   │   ├── agents.py         # BaseAgent class
│   │   ├── agent_implementations.py
│   │   ├── delegator.py      # Task manager
│   │   ├── verifier.py       # Independent auditor
│   │   └── workers.py        # Specialized workers
│   ├── security/             # Safety & auth
│   │   ├── guardrails.py     # Injection defense
│   │   ├── credential_shim.py # Secure credential injection
│   │   ├── agent_identity.py  # Agent authentication
│   │   └── hitl.py           # Human-in-the-loop
│   ├── cognition/            # Reasoning & memory
│   │   ├── reasoning.py      # ReAct, CoT, ToT
│   │   ├── reflection.py     # Self-critique
│   │   └── memory.py         # Episodic & semantic memory
│   ├── infrastructure/       # Utilities
│   │   ├── llm_client.py     # Mistral integration
│   │   ├── tracer.py         # Execution tracing
│   │   └── agent_monitor.py  # Anomaly detection
│   ├── tools/                # Agent tools
│   ├── templates/            # Jinja2 templates
│   ├── logic_blocks/         # Reusable content logic
│   └── main.py               # Entry point
├── tests/                    # 174 test cases
├── docs/                     # Documentation
├── output/                   # Generated content
└── requirements.txt
```

---

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=skincare_agent_system --cov-report=html

# Run specific test suite
pytest tests/test_proposals.py -v
```

### Code Quality

```bash
# Format code
black skincare_agent_system/

# Sort imports
isort skincare_agent_system/

# Lint
flake8 skincare_agent_system/

# Pre-commit hooks
pre-commit install
pre-commit run --all-files
```

### CI/CD

The project uses GitHub Actions for:
- Automated testing on push/PR
- Code quality checks (Black, flake8)
- Coverage reporting

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Coding Standards

- Follow PEP 8 style guide
- Use type hints for all function signatures
- Write docstrings for all public methods
- Maintain test coverage above 80%
- Update documentation for new features

---

## License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## Acknowledgments

- Built with [LangGraph](https://github.com/langchain-ai/langgraph) for workflow orchestration
- Powered by [Mistral AI](https://mistral.ai/) for LLM capabilities
- Inspired by advanced agentic AI research and multi-agent systems design

---

## Support

For issues, questions, or contributions:
- Open an issue on GitHub
- Review the [Project Documentation](docs/projectdocumentation.md)
- Check the [Implementation Guide](IMPLEMENTATION.md)
