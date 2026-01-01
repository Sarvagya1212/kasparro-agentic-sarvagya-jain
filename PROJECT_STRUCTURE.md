# Project Structure

## Clean, Production-Ready Layout

```
kasparro-content-generation/
├── skincare_agent_system/
│   ├── __init__.py
│   ├── main.py                  # Entry: orchestrator.run()
│   ├── orchestrator.py          # State-machine routing
│   ├── models.py                # Pydantic models, AgentStatus
│   ├── agents.py                # BaseAgent class
│   ├── agent_implementations.py # DataAgent, AnalysisAgent, etc.
│   ├── tools/
│   │   ├── __init__.py          # BaseTool, ToolRegistry
│   │   └── content_tools.py     # BenefitsTool, FAQTool, etc.
│   ├── logic_blocks/
│   │   ├── benefits_block.py
│   │   ├── usage_block.py
│   │   ├── comparison_block.py
│   │   └── question_generator.py
│   ├── templates/
│   │   ├── base_template.py
│   │   ├── faq_template.py
│   │   ├── product_page_template.py
│   │   └── comparison_template.py
│   ├── data/
│   │   └── products.py          # GlowBoost + RadiancePlus
│   └── README.md                # Architecture blueprint
│
├── tests/
│   ├── test_retry_loop.py       # RETRY mechanism test
│   └── test_dynamic_flow.py     # Dynamic routing test
│
├── output/
│   ├── faq.json                 # ✅ 15 questions
│   ├── product_page.json        # ✅ ₹699, 10%
│   └── comparison_page.json     # ✅ Side-by-side
│
├── docs/
│   └── projectdocumentation.md
│
├── README.md                    # Main documentation
├── IMPLEMENTATION.md            # Implementation summary
└── requirements.txt
```

## Key Files

| File | Purpose |
|------|---------|
| `main.py` | Single `orchestrator.run()` entry point |
| `orchestrator.py` | State-machine with RETRY loop-back |
| `models.py` | `AgentContext`, `AgentStatus` enum |
| `agent_implementations.py` | All 5 agents |
| `tools/content_tools.py` | ToolRegistry for agent autonomy |

## Run Commands

```bash
python -m skincare_agent_system.main
python tests/test_retry_loop.py
```
