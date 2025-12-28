# Kasparro AI - Multi-Agent Content Generation System

[![CI/CD](https://github.com/yourusername/kasparro-ai-agentic-content-generation-system/actions/workflows/ci.yml/badge.svg)](https://github.com/Sarvagya1212/kasparro-agentic-sarvagya-jain/actions)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **Applied AI Engineer Assignment** - Multi-Agent Content Generation System

A production-ready, modular agentic automation system that generates structured, machine-readable skincare product content through a deterministic pipeline of logic blocks and templates.

## 🎯 What This System Does

Transforms product data → Structured JSON content pages

**Input:** GlowBoost Vitamin C Serum product data
**Output:** 3 JSON files (FAQ, Product Page, Comparison)
**Method:** Logic blocks + Templates (NOT LLM prompts)

## ✨ Key Features

- ✅ **Multi-Agent Architecture** - Clear separation: Logic Blocks → Templates → Output
- ✅ **Custom Template System** - NOT LLM prompts, actual template protocol
- ✅ **Reusable Logic Blocks** - 4 independent, composable modules
- ✅ **Deterministic Output** - Same input = Same output, every time
- ✅ **15+ Categorized Questions** - Across 6 categories (Informational, Usage, Safety, etc.)
- ✅ **Zero External Dependencies** - No API calls, no LLM required
- ✅ **Production-Ready** - Type-safe, tested, documented

## 🚀 Quick Start

### Installation

```bash
# Clone repository
git clone https://github.com/yourusername/kasparro-ai-agentic-content-generation-system.git
cd kasparro-ai-agentic-content-generation-system

# Install dependencies (optional - for testing)
pip install -r requirements.txt
```

### Run the Pipeline

```bash
python skincare_agent_system/generate_content.py
```

**Output:**
```
✓ Generated 15 questions → output/faq.json
✓ Generated product page → output/product_page.json
✓ Generated comparison → output/comparison_page.json
```

## 📊 System Architecture

```
┌─────────────────────────────────────────────┐
│         GlowBoost Product Data              │
└──────────────┬──────────────────────────────┘
               │
       ┌───────┴────────┐
       │                │
   ┌───▼────┐      ┌────▼────┐
   │ Logic  │      │Templates│
   │ Blocks │      │         │
   └───┬────┘      └────┬────┘
       │                │
       └────────┬───────┘
                │
         ┌──────▼───────┐
         │ JSON Outputs │
         └──────────────┘
```

### Components

**Logic Blocks** (`logic_blocks/`)
- `benefits_block.py` - Extract and format benefits
- `usage_block.py` - Extract and format usage instructions
- `comparison_block.py` - Compare products (ingredients, price, benefits)
- `question_generator.py` - Generate 15+ categorized FAQ questions

**Templates** (`templates/`)
- `faq_template.py` - FAQ page structure
- `product_page_template.py` - Product page structure
- `comparison_template.py` - Comparison page structure

**Data** (`data/`)
- `products.py` - GlowBoost product + fictional Product B

## 📋 Generated Outputs

### 1. FAQ Page (`faq.json`)

```json
{
  "product": "GlowBoost Vitamin C Serum",
  "total_questions": 15,
  "faqs": [
    {
      "id": 1,
      "question": "What is GlowBoost Vitamin C Serum?",
      "answer": "...",
      "category": "Informational"
    }
  ]
}
```

**Categories:** Informational, Usage, Safety, Purchase, Comparison, Results

### 2. Product Page (`product_page.json`)

```json
{
  "product_info": {
    "name": "GlowBoost Vitamin C Serum",
    "concentration": "10% Vitamin C"
  },
  "benefits": [...],
  "ingredients": {...},
  "usage": {...},
  "pricing": {...}
}
```

### 3. Comparison Page (`comparison_page.json`)

```json
{
  "comparison_type": "side_by_side",
  "primary_product": "GlowBoost Vitamin C Serum",
  "comparison_with": "RadiancePlus Brightening Serum",
  "comparison_table": [...],
  "winner_categories": {...}
}
```

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=skincare_agent_system --cov-report=term

# Run specific test suite
pytest tests/test_logic_blocks.py -v
pytest tests/test_templates.py -v
pytest tests/test_pipeline.py -v
```

**Test Coverage:**
- ✅ Logic blocks unit tests
- ✅ Template unit tests
- ✅ Integration tests
- ✅ Pipeline end-to-end tests

## 📁 Project Structure

```
kasparro-content-generation/
├── skincare_agent_system/
│   ├── data/
│   │   └── products.py              # GlowBoost + Product B
│   ├── logic_blocks/
│   │   ├── benefits_block.py        # Benefits extraction
│   │   ├── usage_block.py           # Usage formatting
│   │   ├── comparison_block.py      # Product comparison
│   │   └── question_generator.py    # FAQ generation
│   ├── templates/
│   │   ├── base_template.py         # Template protocol
│   │   ├── faq_template.py          # FAQ structure
│   │   ├── product_page_template.py # Product structure
│   │   └── comparison_template.py   # Comparison structure
│   └── generate_content.py          # Main pipeline
├── tests/
│   ├── test_logic_blocks.py         # Logic block tests
│   ├── test_templates.py            # Template tests
│   └── test_pipeline.py             # Integration tests
├── output/
│   ├── faq.json                     # Generated FAQ
│   ├── product_page.json            # Generated product page
│   └── comparison_page.json         # Generated comparison
├── docs/
│   └── projectdocumentation.md      # Technical documentation
└── .github/
    └── workflows/
        └── ci.yml                   # CI/CD pipeline
```

## 🎓 Design Principles

### 1. No LLM Prompting
This is **NOT** a prompting system. Content is generated through:
- Rule-based logic blocks
- Template-based rendering
- Deterministic transformations

### 2. Clear Agent Boundaries
Each component has a **single responsibility**:
- Logic blocks: Data transformation
- Templates: Output formatting
- Pipeline: Orchestration

### 3. Reusable & Modular
Logic blocks can be used independently:

```python
from logic_blocks import extract_benefits, compare_prices

benefits = extract_benefits(product_data)
comparison = compare_prices(product_a, product_b)
```

### 4. Extensible
Adding new content types is simple:
1. Create new logic block (if needed)
2. Create new template
3. Add to pipeline

## 📊 Assignment Compliance

| Requirement | Status | Implementation |
|------------|--------|----------------|
| Multi-agent system | ✅ | Logic blocks + Templates + Pipeline |
| Custom templates | ✅ | 3 template classes (NOT LLM prompts) |
| Reusable logic blocks | ✅ | 4 independent modules |
| 15+ questions | ✅ | 15 questions, 6 categories |
| 3 JSON outputs | ✅ | faq, product, comparison |
| GlowBoost data | ✅ | Exact from assignment |
| Fictional Product B | ✅ | RadiancePlus Brightening Serum |
| No LLM prompting | ✅ | Pure logic + templates |
| Autonomous pipeline | ✅ | Single command execution |

## 🔧 Technical Stack

- **Language:** Python 3.9+
- **Architecture:** Multi-agent modular system
- **Templates:** Custom protocol (not Jinja2/LLM)
- **Logic:** Rule-based transformations
- **Output:** JSON (machine-readable)
- **Testing:** pytest with coverage
- **CI/CD:** GitHub Actions

## 📝 Documentation

- **README.md** - This file
- **docs/projectdocumentation.md** - Detailed technical documentation
- **IMPLEMENTATION.md** - Implementation summary
- **EVALUATION.md** - Self-evaluation against rubric

## 🎯 Performance

- **Execution Time:** < 1 second for all 3 outputs
- **Deterministic:** Same input always produces same output
- **No External Calls:** Zero API dependencies
- **Type Safe:** Full Python type hints

## 🤝 Contributing

This is an assignment submission. For questions or feedback, please contact the repository owner.

## 📄 License

MIT License - See LICENSE file for details

## 👤 Author

**Sarvagya Jain**
Applied AI Engineer Assignment
Kasparro

---
