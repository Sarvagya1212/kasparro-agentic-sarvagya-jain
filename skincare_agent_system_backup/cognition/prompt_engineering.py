"""
Prompt Engineering: Optimized prompts with versioning for agents.
Implements few-shot examples, chain-of-thought, and system prompts.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger("PromptEngineering")


class PromptType(Enum):
    """Types of prompts."""

    PROPOSAL = "proposal"
    ANALYSIS = "analysis"
    GENERATION = "generation"
    VALIDATION = "validation"
    REASONING = "reasoning"
    DELEGATION = "delegation"
    REFLECTION = "reflection"
    META = "meta"  # Meta-reasoning for orchestrator


@dataclass
class PromptExample:
    """Few-shot example for prompts."""

    input_text: str
    output_text: str
    explanation: Optional[str] = None


@dataclass
class PromptTemplate:
    """Versioned prompt template."""

    template_id: str
    version: str
    prompt_type: PromptType
    agent_type: str
    system_prompt: str
    user_template: str
    examples: List[PromptExample] = field(default_factory=list)
    output_format: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def render(
        self,
        context: Dict[str, Any],
        include_examples: bool = True,
        include_cot: bool = True,
    ) -> str:
        """Render the prompt with context."""
        parts = []

        # Add few-shot examples if requested
        if include_examples and self.examples:
            parts.append("## Examples\n")
            for i, ex in enumerate(self.examples, 1):
                parts.append(f"Example {i}:")
                parts.append(f"Input: {ex.input_text}")
                parts.append(f"Output: {ex.output_text}")
                if ex.explanation and include_cot:
                    parts.append(f"Reasoning: {ex.explanation}")
                parts.append("")

        # Format user template with context
        try:
            formatted = self.user_template.format(**context)
            parts.append(formatted)
        except KeyError as e:
            logger.warning(f"Missing context key: {e}")
            parts.append(self.user_template)

        # Add output format if specified
        if self.output_format:
            parts.append(f"\n## Output Format\n{self.output_format}")

        # Add chain-of-thought instruction if enabled
        if include_cot:
            parts.append("\nThink step by step before providing your answer.")

        return "\n".join(parts)


# ============ AGENT-SPECIFIC PROMPTS ============

DATA_AGENT_PROPOSAL = PromptTemplate(
    template_id="data_agent_proposal_v2",
    version="2.0",
    prompt_type=PromptType.PROPOSAL,
    agent_type="DataAgent",
    system_prompt=(
        "You are the Data Agent, responsible for loading and validating product data.\n"
        "Your role is to determine if data loading is needed and propose appropriate "
        "actions.\nBe precise about data requirements and validation criteria."
    ),
    user_template="""## Current State
Product Data: {product_loaded}
Comparison Data: {comparison_loaded}
Execution History: {history_length} steps
Last Step: {last_step}

## Your Task
Evaluate if you should load product data now.

## Considerations
1. Has product data already been loaded?
2. Are there any validation errors to address?
3. Is this the appropriate phase for data loading?

Based on this analysis, should you act?""",
    examples=[
        PromptExample(
            input_text="Product Data: Not loaded, 0 steps executed",
            output_text='{"should_act": true, "action": "load_data", "confidence": '
            '0.95, "reason": "No product data - loading is required"}',
            explanation="Data loading is the first step, and no data exists yet",
        ),
        PromptExample(
            input_text="Product Data: Loaded, Analysis complete",
            output_text='{"should_act": false, "action": "none", "confidence": '
            '0.1, "reason": "Data already loaded, workflow past data phase"}',
            explanation="Data is already present, no need to reload",
        ),
    ],
    output_format="""Respond in JSON:
{
    "should_act": true/false,
    "action": "action_name",
    "confidence": 0.0-1.0,
    "reason": "explanation"
}""",
)

DELEGATOR_PROPOSAL = PromptTemplate(
    template_id="delegator_proposal_v2",
    version="2.0",
    prompt_type=PromptType.DELEGATION,
    agent_type="DelegatorAgent",
    system_prompt=(
        "You are the Delegator Agent, a project manager coordinating analysis tasks.\n"
        "Your role is to decompose complex analysis into subtasks and delegate to "
        "specialized workers.\nFocus on task dependencies, optimal ordering, and "
        "worker capabilities."
    ),
    user_template="""## Current State
Product: {product_name}
Comparison Product: {comparison_name}
Analysis Status: {analysis_status}
Completed Tasks: {completed_tasks}
Pending Tasks: {pending_tasks}

## Available Workers
- BenefitsWorker: Extract product benefits
- UsageWorker: Format usage instructions
- FAQWorker: Generate FAQ content
- ComparisonWorker: Compare products
- ValidationWorker: Validate analysis results

## Your Task
Determine next analysis task and assign to appropriate worker.""",
    examples=[
        PromptExample(
            input_text="Analysis: Not started, No completed tasks",
            output_text='{"should_act": true, "action": "delegate_benefits", '
            '"confidence": 0.9, "reason": "Benefits extraction is foundation for '
            'other analysis", "worker": "BenefitsWorker"}',
            explanation="Benefits should be extracted first as other tasks "
            "depend on it",
        )
    ],
    output_format="""Respond in JSON:
{
    "should_act": true/false,
    "action": "action_name",
    "worker": "WorkerName",
    "confidence": 0.0-1.0,
    "reason": "explanation",
    "priority": 1-10
}""",
)

GENERATION_PROPOSAL = PromptTemplate(
    template_id="generation_proposal_v2",
    version="2.0",
    prompt_type=PromptType.GENERATION,
    agent_type="GenerationAgent",
    system_prompt=(
        "You are the Generation Agent, responsible for creating final content.\n"
        "Your role is to evaluate when analysis is complete and generate output "
        "content\n"
        "Ensure all required data is available before generating."
    ),
    user_template="""## Current State
Product: {product_name}
Analysis Complete: {analysis_complete}
Benefits: {benefits_count} items
Questions: {questions_count} generated
Comparison: {comparison_available}
Previous Generation: {already_generated}

## Requirements for Generation
- Product data must be loaded
- Analysis must be complete
- Minimum 15 questions required
- Benefits and usage must be extracted

## Your Task
Determine if content generation should proceed.""",
    output_format="""Respond in JSON:
{
    "should_act": true/false,
    "action": "generate_content",
    "confidence": 0.0-1.0,
    "reason": "explanation"
}""",
)

VERIFIER_PROPOSAL = PromptTemplate(
    template_id="verifier_proposal_v2",
    version="2.0",
    prompt_type=PromptType.VALIDATION,
    agent_type="VerifierAgent",
    system_prompt=(
        "You are the Verifier Agent, an independent auditor ensuring quality.\n"
        "Your role is to validate outputs, check for errors, and ensure safety "
        "compliance.\nBe thorough but not obstructive."
    ),
    user_template="""## Current State
Content Generated: {content_generated}
Files in Output: {output_files}
Validation Status: {validation_status}
Previous Errors: {previous_errors}

## Verification Checks
1. Schema compliance for output JSON
2. Content accuracy and completeness
3. Safety and guidelines compliance
4. Data consistency between files

## Your Task
Determine if verification should run now.""",
    output_format="""Respond in JSON:
{
    "should_act": true/false,
    "action": "verify_outputs",
    "confidence": 0.0-1.0,
    "reason": "explanation"
}""",
)

META_REASONING = PromptTemplate(
    template_id="meta_reasoning_v1",
    version="1.0",
    prompt_type=PromptType.META,
    agent_type="Orchestrator",
    system_prompt="""You are the Meta-Reasoning system for the orchestrator.
Your role is to analyze workflow state and make strategic decisions about:
1. Which agent should run next
2. Whether to form coalitions
3. How to handle failures
4. When the workflow is complete""",
    user_template="""## Workflow State
Step: {step_number} / {max_steps}
Active Goal: {current_goal}
Completed Agents: {completed_agents}
Pending Proposals: {pending_proposals}

## Agent Proposals
{proposals_summary}

## Historical Performance
{agent_performance}

## Strategic Analysis Required
1. Evaluate proposal confidence levels
2. Consider agent historical success rates
3. Identify potential bottlenecks
4. Recommend optimal next action

Provide strategic recommendation.""",
    output_format="""Respond in JSON:
{
    "selected_agent": "AgentName",
    "confidence": 0.0-1.0,
    "reasoning": "strategic explanation",
    "alternative": "backup AgentName",
    "risk_level": "low/medium/high",
    "optimization_hint": "optional suggestion"
}""",
)

REFLECTION_PROMPT = PromptTemplate(
    template_id="reflection_v1",
    version="1.0",
    prompt_type=PromptType.REFLECTION,
    agent_type="Any",
    system_prompt=(
        "You are reflecting on your recent output to identify issues and "
        "improvements.\n"
        "Be critical but constructive. Focus on accuracy, completeness, and quality."
    ),
    user_template="""## Your Recent Output
{output_summary}

## Context
Agent: {agent_name}
Task: {task_description}
Constraints: {constraints}

## Reflection Questions
1. Is the output complete and accurate?
2. Are there any logical errors or inconsistencies?
3. Does it meet all requirements and constraints?
4. What could be improved?

Provide honest self-assessment.""",
    output_format="""Respond in JSON:
{
    "quality_score": 0.0-1.0,
    "issues": ["list of issues"],
    "suggestions": ["list of improvements"],
    "should_retry": true/false,
    "confidence": 0.0-1.0
}""",
)


class PromptRegistry:
    """
    Registry for prompt templates with versioning.
    """

    def __init__(self):
        self._templates: Dict[str, Dict[str, PromptTemplate]] = (
            {}
        )  # id -> version -> template
        self._active_versions: Dict[str, str] = {}  # id -> active version
        self._register_defaults()

    def _register_defaults(self) -> None:
        """Register default prompt templates."""
        defaults = [
            DATA_AGENT_PROPOSAL,
            DELEGATOR_PROPOSAL,
            GENERATION_PROPOSAL,
            VERIFIER_PROPOSAL,
            META_REASONING,
            REFLECTION_PROMPT,
        ]
        for template in defaults:
            self.register(template)

    def register(self, template: PromptTemplate) -> None:
        """Register a prompt template."""
        if template.template_id not in self._templates:
            self._templates[template.template_id] = {}
            self._active_versions[template.template_id] = template.version

        self._templates[template.template_id][template.version] = template
        logger.debug(f"Registered prompt: {template.template_id} v{template.version}")

    def get(
        self, template_id: str, version: Optional[str] = None
    ) -> Optional[PromptTemplate]:
        """Get a prompt template."""
        if template_id not in self._templates:
            return None

        version = version or self._active_versions.get(template_id)
        return self._templates[template_id].get(version)

    def get_for_agent(
        self, agent_type: str, prompt_type: PromptType
    ) -> Optional[PromptTemplate]:
        """Get prompt template for agent type and prompt type."""
        for versions in self._templates.values():
            for template in versions.values():
                if (
                    template.agent_type == agent_type
                    and template.prompt_type == prompt_type
                ):
                    return template
        return None

    def set_active_version(self, template_id: str, version: str) -> bool:
        """Set the active version for a template."""
        if template_id in self._templates and version in self._templates[template_id]:
            self._active_versions[template_id] = version
            return True
        return False

    def list_versions(self, template_id: str) -> List[str]:
        """List all versions of a template."""
        if template_id in self._templates:
            return list(self._templates[template_id].keys())
        return []

    def list_templates(self) -> List[Dict[str, Any]]:
        """List all registered templates."""
        result = []
        for template_id, versions in self._templates.items():
            active = self._active_versions.get(template_id)
            template = versions.get(active)
            if template:
                result.append(
                    {
                        "id": template_id,
                        "active_version": active,
                        "versions": list(versions.keys()),
                        "type": template.prompt_type.value,
                        "agent": template.agent_type,
                    }
                )
        return result


# Singleton
_prompt_registry: Optional[PromptRegistry] = None


def get_prompt_registry() -> PromptRegistry:
    """Get or create prompt registry singleton."""
    global _prompt_registry
    if _prompt_registry is None:
        _prompt_registry = PromptRegistry()
    return _prompt_registry


def render_prompt(
    template_id: str,
    context: Dict[str, Any],
    version: Optional[str] = None,
    include_examples: bool = True,
) -> str:
    """Convenience function to render a prompt."""
    registry = get_prompt_registry()
    template = registry.get(template_id, version)
    if template:
        return template.render(context, include_examples)
    return ""


def get_agent_prompt(
    agent_type: str,
    context: Dict[str, Any],
    prompt_type: PromptType = PromptType.PROPOSAL,
) -> tuple:
    """
    Get system and user prompts for an agent.

    Returns:
        (system_prompt, user_prompt) tuple
    """
    registry = get_prompt_registry()
    template = registry.get_for_agent(agent_type, prompt_type)

    if template:
        return (template.system_prompt, template.render(context, include_examples=True))

    # Fallback
    return (f"You are the {agent_type}.", f"Current context: {json.dumps(context)}")
